import docker
import logging
import os
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from aistack.schemas.apps import AppStatusEnum, AppVolume, AppURL

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
                       memory_limit: Optional[str] = None, cpu_limit: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
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
                container_config['environment'] = environment
            
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
            
            # 启动容器
            container = self.client.containers.run(**container_config)
            
            logger.info(f"容器启动成功: {container.id}")
            return True, f"容器启动成功: {container.id}", container.id
            
        except Exception as e:
            error_msg = f"容器启动失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
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
        获取容器资源使用统计
        
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
            
            return True, "获取统计信息成功", stats_info
            
        except docker.errors.NotFound:
            return False, f"容器不存在: {container_id}", None
        except Exception as e:
            error_msg = f"获取容器统计信息失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
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