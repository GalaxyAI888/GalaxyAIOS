import docker
import logging
import os
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from aistack.schemas.apps import AppStatusEnum, AppVolume, AppURL
import subprocess
import shlex

logger = logging.getLogger(__name__)


class DockerManager:
    """Docker管理工具类"""
    
    def __init__(self):
        """初始化Docker客户端"""
        try:
            self.client = docker.from_env()
            logger.info("Docker客户端初始化成功")
        except Exception as e:
            logger.error(f"Docker客户端初始化失败: {e}")
            raise
    
    def _check_build_context_permissions(self, dockerfile_dir: str) -> Tuple[bool, str]:
        """
        检查构建上下文目录的权限
        
        Args:
            dockerfile_dir: Dockerfile所在目录
            
        Returns:
            (是否可访问, 错误信息)
        """
        try:
            # 检查目录是否存在
            if not os.path.exists(dockerfile_dir):
                return False, f"构建上下文目录不存在: {dockerfile_dir}"
            
            # 检查目录权限
            if not os.access(dockerfile_dir, os.R_OK):
                return False, f"没有读取构建上下文目录的权限: {dockerfile_dir}"
            
            # 检查目录是否可执行（对于Docker构建很重要）
            if not os.access(dockerfile_dir, os.X_OK):
                return False, f"没有执行构建上下文目录的权限: {dockerfile_dir}"
            
            # 检查Docker是否可以访问该目录
            # 在Linux系统上，检查目录所有者
            if os.name == 'posix':
                try:
                    import pwd
                    import grp
                    
                    # 获取当前用户信息
                    current_uid = os.getuid()
                    current_gid = os.getgid()
                    
                    # 获取目录所有者信息
                    dir_stat = os.stat(dockerfile_dir)
                    dir_uid = dir_stat.st_uid
                    dir_gid = dir_stat.st_gid
                    
                    # 检查当前用户是否是目录所有者
                    if dir_uid != current_uid:
                        # 检查当前用户是否在docker组中
                        try:
                            docker_group = grp.getgrnam('docker')
                            if current_gid not in [g.gr_gid for g in [grp.getgrgid(gid) for gid in os.getgroups()]]:
                                logger.warning(f"当前用户可能没有足够的权限访问目录: {dockerfile_dir}")
                                logger.warning("建议将目录权限设置为当前用户可访问")
                        except (KeyError, ImportError):
                            logger.warning("无法检查docker组权限")
                            
                except (ImportError, OSError):
                    logger.warning("无法检查用户权限信息")
            
            return True, "权限检查通过"
            
        except Exception as e:
            return False, f"权限检查失败: {e}"

    def build_image(self, dockerfile_path: str, image_name: str, image_tag: str = "latest", 
                   build_args: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        构建Docker镜像
        
        Args:
            dockerfile_path: Dockerfile路径
            image_name: 镜像名称
            image_tag: 镜像标签
            build_args: 构建参数
            
        Returns:
            (成功标志, 消息)
        """
        try:
            logger.info(f"开始构建镜像: {image_name}:{image_tag}")
            
            # 检查Dockerfile是否存在
            if not os.path.exists(dockerfile_path):
                return False, f"Dockerfile不存在: {dockerfile_path}"
            
            # 检查Dockerfile是否是文件而不是目录
            if os.path.isdir(dockerfile_path):
                return False, f"Dockerfile路径指向一个目录而不是文件: {dockerfile_path}"
            
            # 获取Dockerfile所在目录
            dockerfile_dir = os.path.dirname(os.path.abspath(dockerfile_path))
            dockerfile_name = os.path.basename(dockerfile_path)
            
            # 检查构建上下文权限
            context_ok, context_error = self._check_build_context_permissions(dockerfile_dir)
            if not context_ok:
                return False, context_error
            
            # 检查Dockerfile权限
            if not os.access(dockerfile_path, os.R_OK):
                return False, f"没有读取Dockerfile的权限: {dockerfile_path}"
            
            # 验证Dockerfile内容
            try:
                with open(dockerfile_path, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return False, f"Dockerfile内容为空: {dockerfile_path}"
                    
                    # 检查是否包含Dockerfile的基本指令
                    if not any(keyword in content.upper() for keyword in ['FROM', 'RUN', 'CMD', 'ENTRYPOINT', 'COPY', 'ADD']):
                        logger.warning(f"Dockerfile可能不是有效的: {dockerfile_path}")
                        logger.warning(f"Dockerfile内容前100字符: {content[:100]}")
            except Exception as e:
                return False, f"无法读取Dockerfile内容: {e}"
            
            logger.info(f"构建上下文目录: {dockerfile_dir}")
            logger.info(f"Dockerfile名称: {dockerfile_name}")
            logger.info(f"Dockerfile完整路径: {dockerfile_path}")
            
            # 构建镜像，添加更多错误处理
            try:
                logger.info(f"开始Docker构建，上下文目录: {dockerfile_dir}")
                logger.info(f"Dockerfile名称: {dockerfile_name}")
                
                # 简化构建调用，移除可能导致问题的参数
                image, build_logs = self.client.images.build(
                    path=dockerfile_dir,
                    dockerfile=dockerfile_name,
                    tag=f"{image_name}:{image_tag}",
                    buildargs=build_args or {},
                    rm=True  # 构建完成后删除中间容器
                )
                
                # 简化日志处理
                logger.info(f"构建完成，镜像标签: {image.tags}")
                return True, f"镜像构建成功: {image.tags[0]}"
                
            except docker.errors.BuildError as e:
                error_msg = f"镜像构建失败: {e}"
                logger.error(error_msg)
                # 简化错误日志处理
                if hasattr(e, 'build_log') and e.build_log:
                    logger.error("构建错误日志:")
                    for log in e.build_log:
                        if isinstance(log, dict):
                            if 'error' in log:
                                logger.error(f"错误: {log['error']}")
                            elif 'stream' in log:
                                logger.error(f"日志: {log['stream'].strip()}")
                        else:
                            logger.error(f"日志: {log}")
                return False, error_msg
                
        except docker.errors.APIError as e:
            error_msg = f"Docker API错误: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"镜像构建失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def pull_image(self, image_name: str, image_tag: str = "latest") -> Tuple[bool, str]:
        """
        拉取Docker镜像
        
        Args:
            image_name: 镜像名称（可以是完整地址）
            image_tag: 镜像标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            full_image_name = f"{image_name}:{image_tag}"
            logger.info(f"开始拉取镜像: {full_image_name}")
            
            # 拉取镜像
            image = self.client.images.pull(image_name, tag=image_tag)
            
            logger.info(f"镜像拉取成功: {image.tags}")
            return True, f"镜像拉取成功: {image.tags[0]}"
            
        except Exception as e:
            error_msg = f"镜像拉取失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_image_info(self, image_name: str, image_tag: str = "latest") -> Tuple[bool, str, Optional[Dict]]:
        """
        获取镜像信息
        
        Args:
            image_name: 镜像名称
            image_tag: 镜像标签
            
        Returns:
            (成功标志, 消息, 镜像信息)
        """
        try:
            full_image_name = f"{image_name}:{image_tag}"
            image = self.client.images.get(full_image_name)
            
            image_info = {
                'id': image.id,
                'tags': image.tags,
                'size': image.attrs['Size'],
                'created': image.attrs['Created'],
                'architecture': image.attrs['Architecture'],
                'os': image.attrs['Os']
            }
            
            return True, "获取镜像信息成功", image_info
            
        except docker.errors.ImageNotFound:
            return False, f"镜像不存在: {full_image_name}", None
        except Exception as e:
            error_msg = f"获取镜像信息失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def start_container(self, app_name: str, image_name: str, image_tag: str = "latest",
                       container_name: Optional[str] = None, ports: Optional[Dict[str, str]] = None,
                       environment: Optional[Dict[str, str]] = None, volumes: Optional[List[AppVolume]] = None,
                       memory_limit: Optional[str] = None, cpu_limit: Optional[str] = None,
                       gpu_devices: Optional[List[int]] = None, device_type: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        启动Docker容器
        
        Args:
            app_name: 应用名称
            image_name: 镜像名称
            image_tag: 镜像标签
            container_name: 容器名称
            ports: 端口映射
            environment: 环境变量
            volumes: 卷映射
            memory_limit: 内存限制
            cpu_limit: CPU限制
            gpu_devices: GPU设备索引列表，如[0, 1]表示使用第0和第1个设备
            device_type: 设备类型（例如 "cuda"|"rocm"|"dcu"|"npu"|"musa"），默认自动探测
            
        Returns:
            (成功标志, 消息, 容器ID)
        """
        try:
            logger.info(f"开始启动容器: {app_name}")
            
            # 检查镜像是否存在
            try:
                image = self.client.images.get(f"{image_name}:{image_tag}")
            except docker.errors.ImageNotFound:
                return False, f"镜像不存在: {image_name}:{image_tag}", None
            
            # 准备容器配置
            container_config = {
                'image': f"{image_name}:{image_tag}",
                'name': container_name or f"{app_name}-{int(time.time())}",
                'detach': True,  # 后台运行
                'restart_policy': {"Name": "unless-stopped"}
            }
            
            # 添加端口映射
            if ports:
                container_config['ports'] = ports
            
            # 添加环境变量
            if environment:
                container_config['environment'] = dict(environment)
            else:
                container_config['environment'] = {}
            
            # 添加卷映射
            if volumes:
                volume_mounts = {}
                for volume in volumes:
                    # 处理卷映射，支持字典和对象两种格式
                    if isinstance(volume, dict):
                        host_path = volume.get('host_path')
                        container_path = volume.get('container_path')
                        read_only = volume.get('read_only', False)
                    else:
                        # 如果是 AppVolume 对象
                        host_path = volume.host_path
                        container_path = volume.container_path
                        read_only = volume.read_only
                    
                    if host_path and container_path:
                        # 智能处理路径：如果是相对路径，转换为绝对路径
                        import os
                        if not os.path.isabs(host_path):
                            # 相对路径，转换为绝对路径
                            host_path = os.path.abspath(host_path)
                            logger.info(f"相对路径转换为绝对路径: {host_path}")
                        
                        # 确保主机目录存在
                        os.makedirs(host_path, exist_ok=True)
                        volume_mounts[host_path] = {
                            'bind': container_path,
                            'mode': 'ro' if read_only else 'rw'
                        }
                container_config['volumes'] = volume_mounts
            
            # 添加资源限制
            if memory_limit or cpu_limit:
                container_config['mem_limit'] = memory_limit
                container_config['cpu_quota'] = int(float(cpu_limit) * 100000) if cpu_limit else None
                container_config['cpu_period'] = 100000
            
            # 添加GPU/NPU等设备配置
            if gpu_devices:
                # 归一化类型（应由上层基于采集数据推断并传入；此处不再做仅CUDA的特例推断）
                dtype = (device_type or "").lower().strip() if device_type else None

                gpu_device_str = ",".join(map(str, gpu_devices))

                # CUDA / NVIDIA
                if dtype == "cuda":
                    try:
                        container_config['device_requests'] = [
                            docker.types.DeviceRequest(
                                count=-1,
                                capabilities=[["gpu"]],
                                options={"device": gpu_device_str}
                            )
                        ]
                        # 兼容环境变量
                        env_map = container_config['environment']
                        env_map.setdefault("NVIDIA_VISIBLE_DEVICES", gpu_device_str)
                        env_map.setdefault("NVIDIA_DRIVER_CAPABILITIES", "compute,utility")
                        logger.info(f"配置CUDA设备: {gpu_device_str}")
                    except Exception as e:
                        logger.warning(f"配置CUDA设备失败: {e}")

                # AMD ROCm / DCU（简化处理：挂载kfd和dri，并使用HIP_VISIBLE_DEVICES）
                elif dtype in ("rocm", "dcu"):
                    try:
                        devices = container_config.get('devices', [])
                        # 常见设备节点（存在才挂载）
                        for dev in ["/dev/kfd", "/dev/dri"]:
                            if os.path.exists(dev):
                                devices.append(f"{dev}:{dev}:")
                        if devices:
                            container_config['devices'] = devices
                        # 某些平台需要加入video组
                        try:
                            if os.name == 'posix':
                                group_add = container_config.get('group_add', [])
                                group_add.append('video')
                                container_config['group_add'] = group_add
                        except Exception:
                            pass
                        # 通过环境变量控制可见设备
                        env_map = container_config['environment']
                        env_map.setdefault("HIP_VISIBLE_DEVICES", gpu_device_str)
                        # 兼容变量
                        env_map.setdefault("ROCR_VISIBLE_DEVICES", gpu_device_str)
                        logger.info(f"配置ROCm/DCU设备: {gpu_device_str}")
                    except Exception as e:
                        logger.warning(f"配置ROCm/DCU设备失败: {e}")

                # 华为 NPU（Ascend），仅设置可见设备的环境变量，设备节点挂载因发行版差异较大，这里不强制
                elif dtype == "npu":
                    try:
                        env_map = container_config['environment']
                        env_map.setdefault("ASCEND_VISIBLE_DEVICES", gpu_device_str)
                        logger.info(f"配置NPU设备: {gpu_device_str}")
                    except Exception as e:
                        logger.warning(f"配置NPU设备失败: {e}")

                # MUSA（Moore Threads），以环境变量约定方式暴露
                elif dtype == "musa":
                    try:
                        env_map = container_config['environment']
                        # 常见可见设备变量命名，具体以镜像内运行时为准
                        env_map.setdefault("MUSA_VISIBLE_DEVICES", gpu_device_str)
                        env_map.setdefault("MTHREADS_VISIBLE_DEVICES", gpu_device_str)
                        logger.info(f"配置MUSA设备: {gpu_device_str}")
                    except Exception as e:
                        logger.warning(f"配置MUSA设备失败: {e}")

                elif dtype is None:
                    logger.warning("未提供或未推断到 device_type，跳过设备分配（容器将不挂载加速设备）")
                else:
                    logger.warning(f"未识别的设备类型: {device_type}，跳过设备分配")

            # 输出等效 docker run 命令，便于排查
            try:
                equivalent_cmd = self._build_equivalent_docker_run_cmd(container_config)
                logger.info(f"等效 docker run 命令: {equivalent_cmd}")
            except Exception as e:
                logger.debug(f"生成等效 docker run 命令失败: {e}")
            
            # 启动容器
            container = self.client.containers.run(**container_config)
            
            logger.info(f"容器启动成功: {container.id}")
            return True, f"容器启动成功: {container.id}", container.id
            
        except Exception as e:
            error_msg = f"容器启动失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def _build_equivalent_docker_run_cmd(self, container_config: Dict) -> str:
        """根据 container_config 构建用于日志展示的等效 docker run 命令字符串。"""
        parts: List[str] = ["docker", "run", "-d"]

        # restart policy
        rp = container_config.get('restart_policy') or {}
        if isinstance(rp, dict):
            name = rp.get('Name')
            if name:
                parts += ["--restart", name]

        # name
        if container_config.get('name'):
            parts += ["--name", shlex.quote(container_config['name'])]

        # ports
        ports = container_config.get('ports') or {}
        if isinstance(ports, dict):
            for container_port, host_map in ports.items():
                try:
                    # container_port 形如 "80/tcp" 或 80
                    cport = str(container_port).split('/')[0]
                    host_port = None
                    if isinstance(host_map, str):
                        # 形如 "0.0.0.0:8080" 或 "8080"
                        host_port = host_map.split(':')[-1]
                    elif isinstance(host_map, list) and host_map:
                        # 取第一个映射
                        item = host_map[0]
                        if isinstance(item, dict):
                            host_port = item.get('HostPort') or item.get('host_port')
                        else:
                            host_port = str(item).split(':')[-1]
                    elif isinstance(host_map, dict):
                        host_port = host_map.get('HostPort') or host_map.get('host_port')
                    if host_port:
                        parts += ["-p", f"{host_port}:{cport}"]
                except Exception:
                    continue

        # volumes
        volumes = container_config.get('volumes') or {}
        if isinstance(volumes, dict):
            for host_path, spec in volumes.items():
                try:
                    bind = spec.get('bind')
                    mode = spec.get('mode', 'rw')
                    if bind:
                        parts += ["-v", f"{host_path}:{bind}:{mode}"]
                except Exception:
                    continue

        # devices (ROCm/DCU)
        devices = container_config.get('devices') or []
        for dev in devices:
            parts += ["--device", dev]

        # group_add
        group_add = container_config.get('group_add') or []
        for grp in group_add:
            parts += ["--group-add", str(grp)]

        # environment
        envs = container_config.get('environment') or {}
        if isinstance(envs, dict):
            for k, v in envs.items():
                parts += ["-e", f"{k}={shlex.quote(str(v))}"]

        # CUDA --gpus (当存在 device_requests 且配置了 options.device)
        dreqs = container_config.get('device_requests') or []
        if dreqs:
            try:
                # docker-py DeviceRequest 无法直接序列化，这里仅支持常见 CUDA 的 options.device
                for dr in dreqs:
                    opts = getattr(dr, 'options', None) or {}
                    device = opts.get('device')
                    if device:
                        parts += ["--gpus", f"\"device={device}\""]
                        break
            except Exception:
                pass

        # image
        image = container_config.get('image') or ''
        parts.append(shlex.quote(image))

        return " ".join(parts)

    def stop_container(self, container_id: str) -> Tuple[bool, str]:
        """
        停止Docker容器
        
        Args:
            container_id: 容器ID
            
        Returns:
            (成功标志, 消息)
        """
        try:
            logger.info(f"开始停止容器: {container_id}")
            
            container = self.client.containers.get(container_id)
            container.stop(timeout=30)  # 30秒超时
            
            logger.info(f"容器停止成功: {container_id}")
            return True, f"容器停止成功: {container_id}"
            
        except docker.errors.NotFound:
            return False, f"容器不存在: {container_id}"
        except Exception as e:
            error_msg = f"容器停止失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def remove_container(self, container_id: str) -> Tuple[bool, str]:
        """
        删除Docker容器
        
        Args:
            container_id: 容器ID
            
        Returns:
            (成功标志, 消息)
        """
        try:
            logger.info(f"开始删除容器: {container_id}")
            
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            
            logger.info(f"容器删除成功: {container_id}")
            return True, f"容器删除成功: {container_id}"
            
        except docker.errors.NotFound:
            return False, f"容器不存在: {container_id}"
        except Exception as e:
            error_msg = f"容器删除失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_container_status(self, container_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取容器状态
        
        Args:
            container_id: 容器ID
            
        Returns:
            (成功标志, 消息, 状态信息)
        """
        try:
            container = self.client.containers.get(container_id)
            container_info = container.attrs
            
            # 处理端口信息，将Docker的复杂格式转换为简单的字符串映射
            raw_ports = container_info['NetworkSettings']['Ports']
            processed_ports = {}
            if raw_ports:
                for container_port, host_bindings in raw_ports.items():
                    if host_bindings:
                        # 取第一个主机绑定
                        host_binding = host_bindings[0]
                        processed_ports[container_port] = f"{host_binding['HostIp']}:{host_binding['HostPort']}"
                    else:
                        processed_ports[container_port] = ""
            
            status_info = {
                'status': container_info['State']['Status'],
                'running': container_info['State']['Running'],
                'started_at': container_info['State']['StartedAt'],
                'finished_at': container_info['State']['FinishedAt'],
                'error': container_info['State'].get('Error', ''),
                'exit_code': container_info['State'].get('ExitCode'),
                'ip_address': container_info['NetworkSettings']['IPAddress'],
                'ports': processed_ports
            }
            
            return True, "获取状态成功", status_info
            
        except docker.errors.NotFound:
            return False, f"容器不存在: {container_id}", None
        except Exception as e:
            error_msg = f"获取容器状态失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def get_container_stats(self, container_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取容器资源使用统计（包括GPU，如果有NVIDIA GPU）
        
        Args:
            container_id: 容器ID
            
        Returns:
            (成功标志, 消息, 统计信息)
        """
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # 计算CPU使用率
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            cpu_usage = (cpu_delta / system_delta) * stats['cpu_stats']['online_cpus'] * 100.0
            
            # 计算内存使用
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            stats_info = {
                'cpu_usage': round(cpu_usage, 2),
                'memory_usage': f"{memory_usage / (1024*1024):.1f}MB",
                'memory_limit': f"{memory_limit / (1024*1024):.1f}MB",
                'memory_percent': round(memory_percent, 2)
            }
            
            # 检查是否有NVIDIA GPU
            def has_nvidia_gpu():
                return self._has_nvidia_gpu()
            
            if has_nvidia_gpu():
                # 获取容器主进程PID
                pid = container.attrs['State'].get('Pid')
                if pid and pid > 0:
                    try:
                        # 获取GPU总显存信息
                        gpu_info_out = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,memory.total,memory.used,utilization.gpu,name', '--format=csv,noheader,nounits'])
                        gpu_info_lines = gpu_info_out.decode().strip().split('\n')
                        gpu_total_info = {}
                        for line in gpu_info_lines:
                            parts = [x.strip() for x in line.split(',')]
                            if len(parts) == 5:
                                gpu_uuid = parts[0]
                                total_memory = int(parts[1])
                                used_memory = int(parts[2])
                                gpu_utilization = int(parts[3])
                                gpu_name = parts[4]
                                gpu_total_info[gpu_uuid] = {
                                    'total_memory_MB': total_memory,
                                    'used_memory_MB': used_memory,
                                    'gpu_utilization_percent': gpu_utilization,
                                    'gpu_name': gpu_name
                                }
                        
                        # 获取容器进程的GPU使用情况
                        smi_out = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,used_memory,gpu_uuid', '--format=csv,noheader,nounits'])
                        smi_lines = smi_out.decode().strip().split('\n')
                        gpu_stats = []
                        for line in smi_lines:
                            parts = [x.strip() for x in line.split(',')]
                            if len(parts) == 3 and str(pid) == parts[0]:
                                gpu_uuid = parts[2]
                                container_used_memory = int(parts[1])
                                
                                # 获取该GPU的总信息
                                gpu_total = gpu_total_info.get(gpu_uuid, {})
                                total_memory = gpu_total.get('total_memory_MB', 0)
                                gpu_utilization = gpu_total.get('gpu_utilization_percent', 0)
                                gpu_name = gpu_total.get('gpu_name', 'Unknown')
                                
                                # 计算显存占用百分比
                                memory_percent = (container_used_memory / total_memory * 100) if total_memory > 0 else 0
                                
                                gpu_stats.append({
                                    'gpu_uuid': gpu_uuid,
                                    'gpu_name': gpu_name,
                                    'used_memory_MB': container_used_memory,
                                    'total_memory_MB': total_memory,
                                    'memory_percent': round(memory_percent, 2),
                                    'gpu_utilization_percent': gpu_utilization
                                })
                        
                        if gpu_stats:
                            stats_info['gpu'] = gpu_stats
                        else:
                            stats_info['gpu'] = []
                    except Exception as e:
                        stats_info['gpu'] = f"获取GPU信息失败: {e}"
                else:
                    stats_info['gpu'] = '未获取到容器主进程PID，无法检测GPU占用'
            
            return True, "获取统计信息成功", stats_info
            
        except docker.errors.NotFound:
            return False, f"容器不存在: {container_id}", None
        except Exception as e:
            error_msg = f"获取容器统计信息失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def _has_nvidia_gpu(self) -> bool:
        """检查是否有NVIDIA GPU"""
        try:
            result = subprocess.run(['nvidia-smi', '-L'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0 and b'GPU' in result.stdout
        except Exception:
            return False
    
    def list_containers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """
        列出容器
        
        Args:
            filters: 过滤条件
            
        Returns:
            容器列表
        """
        try:
            containers = self.client.containers.list(all=True, filters=filters or {})
            container_list = []
            
            for container in containers:
                # 处理端口信息，将Docker的复杂格式转换为简单的字符串映射
                raw_ports = container.attrs['NetworkSettings']['Ports']
                processed_ports = {}
                if raw_ports:
                    for container_port, host_bindings in raw_ports.items():
                        if host_bindings:
                            # 取第一个主机绑定
                            host_binding = host_bindings[0]
                            processed_ports[container_port] = f"{host_binding['HostIp']}:{host_binding['HostPort']}"
                        else:
                            processed_ports[container_port] = ""
                
                container_info = {
                    'id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'created': container.attrs['Created'],
                    'ports': processed_ports
                }
                container_list.append(container_info)
            
            return container_list
            
        except Exception as e:
            logger.error(f"列出容器失败: {e}")
            return []
    
    def list_images(self) -> List[Dict]:
        """
        列出镜像
        
        Returns:
            镜像列表
        """
        try:
            images = self.client.images.list()
            image_list = []
            
            for image in images:
                image_info = {
                    'id': image.id,
                    'tags': image.tags,
                    'created': image.attrs['Created'],
                    'size': image.attrs['Size']
                }
                image_list.append(image_info)
            
            return image_list
            
        except Exception as e:
            logger.error(f"列出镜像失败: {e}")
            return []
    
    def remove_image(self, image_name: str, image_tag: str = "latest") -> Tuple[bool, str]:
        """
        删除镜像
        
        Args:
            image_name: 镜像名称
            image_tag: 镜像标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            logger.info(f"开始删除镜像: {image_name}:{image_tag}")
            
            image = self.client.images.get(f"{image_name}:{image_tag}")
            self.client.images.remove(image.id, force=True)
            
            logger.info(f"镜像删除成功: {image_name}:{image_tag}")
            return True, f"镜像删除成功: {image_name}:{image_tag}"
            
        except docker.errors.ImageNotFound:
            return False, f"镜像不存在: {image_name}:{image_tag}"
        except Exception as e:
            error_msg = f"镜像删除失败: {e}"
            logger.error(error_msg)
            return False, error_msg 