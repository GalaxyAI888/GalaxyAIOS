import logging
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from aistack.collector import GPUResourceCollector
from aistack.schemas.workers import GPUDeviceInfo

logger = logging.getLogger(__name__)


class GPUService:
    """GPU资源管理服务"""
    
    def __init__(self):
        self.collector = GPUResourceCollector()
    
    def get_available_gpus(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的GPU设备信息，包括使用情况
        
        Returns:
            GPU设备列表，包含使用状态
        """
        try:
            
            gpu_devices = self.collector.collect_gpu_resources()
            
            # 获取当前运行的容器及其GPU使用情况
            container_gpu_usage = self._get_container_gpu_usage()
            
            # 构建GPU信息列表
            available_gpus = []
            for gpu in gpu_devices:
                gpu_info = {
                    'index': gpu.index,
                    'name': gpu.name,
                    'vendor': gpu.vendor,
                    'type': gpu.type,
                    'uuid': gpu.uuid or f"gpu_{gpu.index}",  # 如果没有UUID，使用索引作为标识
                    'temperature': gpu.temperature,
                    'memory': {
                        'total': gpu.memory.total if gpu.memory else 0,
                        'used': gpu.memory.used if gpu.memory else 0,
                        'utilization_rate': gpu.memory.utilization_rate if gpu.memory else 0
                    },
                    'core': {
                        'utilization_rate': gpu.core.utilization_rate if gpu.core else 0
                    },
                    'status': 'available',  # 默认状态
                    'used_by_containers': []
                }
                
                # 检查GPU是否被容器使用
                if gpu.uuid in container_gpu_usage:
                    gpu_info['status'] = 'in_use'
                    gpu_info['used_by_containers'] = container_gpu_usage[gpu.uuid]
                
                available_gpus.append(gpu_info)
            
            return available_gpus
            
        except Exception as e:
            logger.error(f"获取GPU信息失败: {e}")
            return []
    
    def _get_container_gpu_usage(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取容器GPU使用情况
        
        Returns:
            GPU UUID -> 容器使用信息列表的映射
        """
        try:
            # 检查是否有NVIDIA GPU
            if not self._has_nvidia_gpu():
                return {}
            
            # 获取所有运行中的容器
            from aistack.utils.docker_manager import DockerManager
            docker_manager = DockerManager()
            containers = docker_manager.client.containers.list()
            
            gpu_usage = {}
            
            for container in containers:
                try:
                    # 获取容器统计信息
                    success, message, stats_info = docker_manager.get_container_stats(container.id)
                    if success and 'gpu' in stats_info and isinstance(stats_info['gpu'], list):
                        for gpu_stat in stats_info['gpu']:
                            gpu_uuid = gpu_stat.get('gpu_uuid')
                            if gpu_uuid:
                                if gpu_uuid not in gpu_usage:
                                    gpu_usage[gpu_uuid] = []
                                
                                gpu_usage[gpu_uuid].append({
                                    'container_id': container.id,
                                    'container_name': container.name,
                                    'used_memory_MB': gpu_stat.get('used_memory_MB', 0),
                                    'memory_percent': gpu_stat.get('memory_percent', 0),
                                    'gpu_utilization_percent': gpu_stat.get('gpu_utilization_percent', 0)
                                })
                    elif success and 'gpu' in stats_info and isinstance(stats_info['gpu'], str):
                        # 处理GPU信息为字符串的情况（错误信息）
                        logger.warning(f"容器 {container.id} GPU信息: {stats_info['gpu']}")
                except Exception as e:
                    logger.warning(f"获取容器 {container.id} GPU使用信息失败: {e}")
                    continue
            
            return gpu_usage
            
        except Exception as e:
            logger.error(f"获取容器GPU使用情况失败: {e}")
            return {}
    
    def _has_nvidia_gpu(self) -> bool:
        """检查是否有NVIDIA GPU"""
        try:
            result = subprocess.run(['nvidia-smi', '-L'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0 and b'GPU' in result.stdout
        except Exception:
            return False
    
    def get_gpu_by_index(self, gpu_index: int) -> Optional[Dict[str, Any]]:
        """
        根据GPU索引获取GPU信息
        
        Args:
            gpu_index: GPU索引
            
        Returns:
            GPU信息，如果不存在返回None
        """
        gpus = self.get_available_gpus()
        for gpu in gpus:
            if gpu['index'] == gpu_index:
                return gpu
        return None
    
    def is_gpu_available(self, gpu_index: int) -> bool:
        """
        检查GPU是否可用（未被占用或占用但容器未运行）
        
        Args:
            gpu_index: GPU索引
            
        Returns:
            是否可用
        """
        gpu = self.get_gpu_by_index(gpu_index)
        if not gpu:
            return False
        
        # 如果GPU状态为available，则可用
        if gpu['status'] == 'available':
            return True
        
        # 如果GPU被占用，检查占用的容器是否还在运行
        if gpu['status'] == 'in_use' and gpu['used_by_containers']:
            from aistack.utils.docker_manager import DockerManager
            docker_manager = DockerManager()
            
            for container_info in gpu['used_by_containers']:
                container_id = container_info['container_id']
                try:
                    container = docker_manager.client.containers.get(container_id)
                    # 如果容器不在运行状态，则认为GPU可用
                    if container.status != 'running':
                        return True
                except Exception:
                    # 容器不存在，认为GPU可用
                    return True
        
        return False
    
    def get_available_gpu_indices(self) -> List[int]:
        """
        获取所有可用的GPU索引列表
        
        Returns:
            可用的GPU索引列表
        """
        gpus = self.get_available_gpus()
        available_indices = []
        
        for gpu in gpus:
            if self.is_gpu_available(gpu['index']):
                available_indices.append(gpu['index'])
        
        return available_indices
