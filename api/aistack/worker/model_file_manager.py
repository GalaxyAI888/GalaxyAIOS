import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import glob
from itertools import chain
import logging
import os
import re
import time
from typing import Dict, Tuple
from multiprocessing import Manager, cpu_count


from aistack.config.config import Config
from aistack.log import setup_logging
from aistack.schemas.model_files import ModelFile, ModelFileUpdate, ModelFileStateEnum
from aistack.schemas.models import SourceEnum
from aistack.client import ClientSet
from aistack.server.bus import Event, EventType
from aistack.utils.file import delete_path
from aistack.worker import downloaders


logger = logging.getLogger(__name__)

max_concurrent_downloads = 5


class ModelFileManager:
    def __init__(
        self,
        worker_id: int,
        clientset: ClientSet,
        cfg: Config,
    ):
        self._worker_id = worker_id
        self._config = cfg
        self._clientset = clientset
        self._active_downloads: Dict[int, Tuple] = {}
        self._download_pool = None

    async def watch_model_files(self):
        self._prerun()
        while True:
            try:
                logger.debug("Started watching model files.")
                await self._clientset.model_files.awatch(
                    callback=self._handle_model_file_event
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Failed to watch model files: {e}")
                await asyncio.sleep(5)

    def _prerun(self):
        self._mp_manager = Manager()
        self._download_pool = ProcessPoolExecutor(
            max_workers=min(max_concurrent_downloads, cpu_count()),
        )

    def _handle_model_file_event(self, event: Event):
        mf = ModelFile.model_validate(event.data)

        if mf.worker_id != self._worker_id:
            # Ignore model files that are not assigned to this worker.
            return

        logger.debug(f"Received model file event: {event.type} {mf.id} {mf.state}")

        if event.type == EventType.DELETED:
            asyncio.create_task(self._handle_deletion(mf))
        elif event.type in {EventType.CREATED, EventType.UPDATED}:
            if mf.state != ModelFileStateEnum.DOWNLOADING:
                return
            self._create_download_task(mf)

    def _update_model_file(self, id: int, **kwargs):
        model_file_public = self._clientset.model_files.get(id=id)

        model_file_update = ModelFileUpdate(**model_file_public.model_dump())
        for key, value in kwargs.items():
            setattr(model_file_update, key, value)

        self._clientset.model_files.update(id=id, model_update=model_file_update)

    
    async def _handle_deletion(self, model_file: ModelFile):
        entry = self._active_downloads.pop(model_file.id, None)
        if entry:
            future, cancel_flag = entry
            logger.info(
                f"Requesting cancellation for deleted model: {model_file.readable_source}(id: {model_file.id})"
            )
            cancel_flag.set()
            
            # 尝试取消 future（只对尚未开始的任务有效）
            if future.cancel():
                logger.info(f"Download task cancelled before starting: {model_file.readable_source}")
            else:
                logger.info(f"Download task already running, waiting for completion: {model_file.readable_source}")
                # 对于已经在运行的下载，我们需要等待它完成或中断
                try:
                    # 等待一小段时间看是否会被检查点中断
                    await asyncio.wait_for(asyncio.wrap_future(future), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning(f"Download still running after 5s, may need manual cleanup: {model_file.readable_source}")
                except Exception as e:
                    logger.debug(f"Future completed with error: {e}")
            
            # 清理已下载的文件（如果存在）
            if model_file.local_dir or model_file.resolved_paths:
                await self._cleanup_orphaned_files(model_file)

        if model_file.cleanup_on_delete:
            await self._delete_model_file(model_file)
    
    async def _cleanup_orphaned_files(self, model_file: ModelFile):
        """清理因取消下载而残留的文件"""
        try:
            # 清理本地目录
            if model_file.local_dir and os.path.exists(model_file.local_dir):
                import shutil
                shutil.rmtree(model_file.local_dir, ignore_errors=True)
                logger.info(f"Cleaned up local directory: {model_file.local_dir}")
            
            # 清理缓存目录中的临时文件
            if hasattr(model_file, 'source') and model_file.source == SourceEnum.OLLAMA_LIBRARY.value:
                if hasattr(model_file, 'ollama_library_model_name') and model_file.ollama_library_model_name:
                    sanitized_name = re.sub(r"[^a-zA-Z0-9]", "_", model_file.ollama_library_model_name)
                    model_path = os.path.join(self._config.cache_dir, "ollama", sanitized_name)
                    # 清理临时文件
                    temp_file = model_path + ".part"
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.info(f"Cleaned up temp file: {temp_file}")
                    # 清理模型文件（如果存在）
                    if os.path.exists(model_path):
                        os.remove(model_path)
                        logger.info(f"Cleaned up model file: {model_path}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup orphaned files: {e}")

    async def _delete_model_file(self, model_file: ModelFile):
        try:
            if model_file.resolved_paths:
                paths = chain.from_iterable(
                    glob.glob(p) if '*' in p else [p] for p in model_file.resolved_paths
                )
                for path in paths:
                    delete_path(path)

            logger.info(
                f"Deleted model file {model_file.readable_source}(id: {model_file.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to delete {model_file.readable_source}(id: {model_file.id}: {e}"
            )
            await self._update_model_file(
                model_file.id,
                state=ModelFileStateEnum.ERROR,
                state_message=f"Deletion failed: {str(e)}",
            )

    def _create_download_task(self, model_file: ModelFile):
        if model_file.id in self._active_downloads:
            return

        cancel_flag = self._mp_manager.Event()

        download_task = ModelFileDownloadTask(model_file, self._config, cancel_flag)
        future = self._download_pool.submit(download_task.run)
        self._active_downloads[model_file.id] = (future, cancel_flag)

        logger.debug(f"Created download task for {model_file.readable_source}")

        async def _check_completion():
            try:
                await asyncio.wrap_future(future)
                logger.info(f"🎉 Download task completed successfully: {model_file.readable_source}")
            except asyncio.CancelledError:
                logger.info(f"⏹️ Download task cancelled: {model_file.readable_source}")
            except Exception as e:
                logger.error(f"💥 Download task failed: {model_file.readable_source} - {e}")
                await self._update_model_file(
                    model_file.id,
                    state=ModelFileStateEnum.ERROR,
                    state_message=str(e),
                )
            finally:
                self._active_downloads.pop(model_file.id, None)
                logger.debug(f"Download task finished for {model_file.readable_source}")

        asyncio.create_task(_check_completion())


class ModelFileDownloadTask:

    def __init__(self, model_file: ModelFile, cfg: Config, cancel_flag):
        self._model_file = model_file
        self._config = cfg
        self._cancel_flag = cancel_flag
    def _get_existing_file_size(self) -> int:
        """获取已下载文件的实际大小"""
        try:
            total_size = 0
            
            # 检查本地目录中的文件
            if self._model_file.local_dir and os.path.exists(self._model_file.local_dir):
                # 如果是整个目录下载，计算目录中所有文件的大小
                if not self._model_file.model_scope_file_path and not self._model_file.huggingface_filename:
                    # 整个目录下载
                    for root, dirs, files in os.walk(self._model_file.local_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.exists(file_path):
                                try:
                                    total_size += os.path.getsize(file_path)
                                except (OSError, IOError) as e:
                                    logger.warning(f"Failed to get size of {file_path}: {e}")
                                    continue
                else:
                    # 单个文件下载，检查特定文件
                    if self._model_file.model_scope_file_path:
                        # ModelScope 单个文件
                        file_path = os.path.join(self._model_file.local_dir, self._model_file.model_scope_file_path)
                        if os.path.exists(file_path):
                            try:
                                total_size += os.path.getsize(file_path)
                            except (OSError, IOError) as e:
                                logger.warning(f"Failed to get size of {file_path}: {e}")
                    elif self._model_file.huggingface_filename:
                        # HuggingFace 单个文件
                        file_path = os.path.join(self._model_file.local_dir, self._model_file.huggingface_filename)
                        if os.path.exists(file_path):
                            try:
                                total_size += os.path.getsize(file_path)
                            except (OSError, IOError) as e:
                                logger.warning(f"Failed to get size of {file_path}: {e}")
            
            # 检查已解析的文件路径
            if self._model_file.resolved_paths:
                for path in self._model_file.resolved_paths:
                    if os.path.exists(path):
                        if os.path.isfile(path):
                            try:
                                total_size += os.path.getsize(path)
                            except (OSError, IOError) as e:
                                logger.warning(f"Failed to get size of {path}: {e}")
                        elif os.path.isdir(path):
                            # 如果是目录，计算目录中所有文件的大小
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    if os.path.exists(file_path):
                                        try:
                                            total_size += os.path.getsize(file_path)
                                        except (OSError, IOError) as e:
                                            logger.warning(f"Failed to get size of {file_path}: {e}")
                                            continue
            
            logger.debug(f"Existing file size for {self._model_file.readable_source}: {total_size} bytes")
            return total_size
            
        except Exception as e:
            logger.warning(f"Failed to calculate existing file size: {e}")
            return 0

    def prerun(self):
        setup_logging(self._config.debug)
        self._clientset = ClientSet(
            base_url=self._config.server_url,
            username=f"system/worker/{self._config.worker_ip}",
            password=self._config.token,
        )

        self._ensure_model_file_size()

        self._last_download_update_time = 0
        
        # 检测已下载文件的实际大小，避免进度计算错误
        self._initial_downloaded_size = self._get_existing_file_size()
        
        logger.debug(f"Initializing task for {self._model_file.readable_source}")
        logger.debug(f"Existing downloaded size: {self._initial_downloaded_size} bytes")
        
        self._update_progress_func = partial(
            self._update_model_file_progress, self._model_file.id
        )
        self._model_file_size = self._model_file.size
        
        # 如果已有部分文件，更新初始进度
        if self._initial_downloaded_size > 0 and self._model_file_size > 0:
            initial_progress = round((self._initial_downloaded_size / self._model_file_size) * 100, 2)
            logger.info(f"Resuming download from {initial_progress}% ({self._initial_downloaded_size}/{self._model_file_size} bytes)")
            self._update_progress_func(initial_progress)
        
        self.hijack_tqdm_progress()


    def run(self):
        try:
            self.prerun()
            self._download_model_file()
        except asyncio.CancelledError:
            logger.info(f"Download cancelled for {self._model_file.readable_source}")
        except Exception as e:
            logger.error(
                f"Download failed for {self._model_file.readable_source}: {str(e)}"
            )
            self._update_model_file(
                self._model_file.id,
                state=ModelFileStateEnum.ERROR,
                state_message=str(e),
            )

    def _download_model_file(self):
        logger.info(f"Starting download of model file: {self._model_file.readable_source}")
        try:
            # 检查是否已被取消
            if self._cancel_flag.is_set():
                logger.info(f"Download cancelled before starting: {self._model_file.readable_source}")
                raise Exception("Download cancelled")
            
            model_paths = downloaders.download_model(
                self._model_file,
                local_dir=self._model_file.local_dir,
                cache_dir=self._config.cache_dir,
                ollama_library_base_url=self._config.ollama_library_base_url,
                huggingface_token=self._config.huggingface_token,
                cancel_flag=self._cancel_flag,
            )
            
            # 再次检查是否已被取消（下载期间可能被取消）
            if self._cancel_flag.is_set():
                logger.info(f"Download cancelled after completion: {self._model_file.readable_source}")
                raise Exception("Download cancelled")
            
            # 更新模型文件状态为完成
            self._update_model_file(
                self._model_file.id,
                state=ModelFileStateEnum.READY,
                download_progress=100,
                resolved_paths=model_paths,
            )
            
            logger.info(f"✅ Download completed successfully: {self._model_file.readable_source}")
            logger.info(f"📁 Downloaded files: {model_paths}")
            
        except Exception as e:
            # 如果被取消，删除已下载的文件
            if self._cancel_flag.is_set():
                logger.info(f"Cleaning up cancelled download files for: {self._model_file.readable_source}")
                self._cleanup_downloaded_files()
            logger.error(f"❌ Download failed for {self._model_file.readable_source}: {e}")
            raise
    
    def _cleanup_downloaded_files(self):
        """清理已下载的文件"""
        try:
            # 清理本地目录
            if self._model_file.local_dir and os.path.exists(self._model_file.local_dir):
                import shutil
                shutil.rmtree(self._model_file.local_dir, ignore_errors=True)
                logger.info(f"Cleaned up local directory: {self._model_file.local_dir}")
            
            # 清理缓存目录中的临时文件
            cache_dir = self._config.cache_dir
            if self._model_file.source == "ollama_library" and self._model_file.ollama_library_model_name:
                sanitized_name = re.sub(r"[^a-zA-Z0-9]", "_", self._model_file.ollama_library_model_name)
                model_path = os.path.join(cache_dir, "ollama", sanitized_name)
                temp_file = model_path + ".part"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"Cleaned up temp file: {temp_file}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup files: {e}")

    def hijack_tqdm_progress(task_self):
        """
        Monkey patch the tqdm progress bar to update the model instance download progress.
        tqdm is used by hf_hub_download under the hood.
        """
        from tqdm import tqdm

        _original_init = (
            tqdm._original_init if hasattr(tqdm, "_original_init") else tqdm.__init__
        )
        _original_update = (
            tqdm._original_update if hasattr(tqdm, "_original_update") else tqdm.update
        )

        def _new_init(self: tqdm, *args, **kwargs):
            kwargs["disable"] = False  # enable the progress bar anyway
            _original_init(self, *args, **kwargs)

            if hasattr(task_self, '_model_file_size'):
                # 不要在这里累积，因为这会重复计算已下载的大小
                # 初始进度已经在prerun中正确设置了
                pass

        def _new_update(self: tqdm, n=1):
            _original_update(self, n)

            if task_self._cancel_flag.is_set():
                raise asyncio.CancelledError("Download cancelled")

            # This is the default for single tqdm downloader like ollama
            # TODO we may want to unify to always get the size before downloading.
            total_size = self.total
            downloaded_size = self.n
            
            if hasattr(task_self, '_model_file_size'):
                # This is summary for group downloading
                total_size = task_self._model_file_size
                
                # 对于整个目录下载，使用tqdm的当前进度加上初始已下载大小
                # 这样可以正确反映断点续传的进度
                initial_downloaded_size = getattr(task_self, '_initial_downloaded_size', 0)
                downloaded_size = initial_downloaded_size + self.n
                
                # 添加调试日志
                logger.debug(f"Progress update: initial={initial_downloaded_size}, tqdm_n={self.n}, total={total_size}, calculated={downloaded_size}")

            try:
                # 计算进度百分比，确保不超过100%
                progress_percent = round((downloaded_size / total_size) * 100, 2)
                
                # 限制进度不超过100%，避免显示超过100%的进度
                if progress_percent > 100:
                    progress_percent = 100.0
                    logger.warning(
                        f"Download progress exceeded 100% for {task_self._model_file.readable_source}: "
                        f"downloaded={downloaded_size}, total={total_size}, progress={progress_percent}%"
                    )

                # 检查是否需要更新进度
                should_update = (
                    # 下载完成时立即更新
                    downloaded_size >= total_size or
                    # 或者距离上次更新超过2秒
                    time.time() - task_self._last_download_update_time >= 2
                )
                
                if should_update:
                    task_self._update_progress_func(progress_percent)
                    task_self._last_download_update_time = time.time()
                    
                    # 如果下载完成，记录成功日志
                    if downloaded_size >= total_size and progress_percent >= 100:
                        logger.info(f"Download progress reached 100% for {task_self._model_file.readable_source}")
                        
            except Exception as e:
                logger.warning(f"Failed to update progress: {e}")

        tqdm.__init__ = _new_init
        tqdm.update = _new_update
        tqdm._original_init = _original_init
        tqdm._original_update = _original_update

    def _ensure_model_file_size(self):
        if self._model_file.size is not None:
            return

        size = downloaders.get_model_file_size(
            self._model_file,
            huggingface_token=self._config.huggingface_token,
            cache_dir=self._config.cache_dir,
            ollama_library_base_url=self._config.ollama_library_base_url,
        )
        self._model_file.size = size
        self._update_model_file(self._model_file.id, size=size)

    def _update_model_file_progress(self, model_file_id: int, progress: float):
        self._update_model_file(model_file_id, download_progress=progress)

    def _update_model_file(self, id: int, **kwargs):
        model_file_public = self._clientset.model_files.get(id=id)

        model_file_update = ModelFileUpdate(**model_file_public.model_dump())
        for key, value in kwargs.items():
            setattr(model_file_update, key, value)

        self._clientset.model_files.update(id=id, model_update=model_file_update)
