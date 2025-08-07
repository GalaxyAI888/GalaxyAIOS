import logging
import socket
from typing import Optional, List
from aistack.detectors.detector_factory import DetectorFactory
from aistack.detectors.custom.custom import Custom
from aistack.schemas.workers import GPUDevicesInfo, GPUDeviceInfo

logger = logging.getLogger(__name__)

class GPUResourceCollector:
    def __init__(self, gpu_devices: Optional[List[GPUDeviceInfo]] = None):
        logger.info("Initializing GPUResourceCollector...")
        if gpu_devices:
            logger.info(f"Using custom GPU devices: {len(gpu_devices)} devices")
            self._detector_factory = DetectorFactory(
                device="custom",
                gpu_detectors={"custom": [Custom(gpu_devices=gpu_devices)]}
            )
        else:
            logger.info("Using automatic GPU detection")
            self._detector_factory = DetectorFactory()
        logger.info("GPUResourceCollector initialization completed")

    def collect_gpu_resources(self) -> GPUDevicesInfo:
        """收集GPU资源信息"""
        logger.info("Starting GPU resource collection...")
        try:
            gpu_devices = self._detector_factory.detect_gpus()
            logger.info(f"GPU resource collection completed, found {len(gpu_devices)} devices")
            return gpu_devices
        except Exception as e:
            logger.error(f"Failed to detect GPU devices: {e}")
            return []

    def collect_system_info(self):
        """收集系统信息"""
        logger.info("Starting system info collection...")
        try:
            system_info = self._detector_factory.detect_system_info()
            logger.info("System info collection completed")
            return system_info
        except Exception as e:
            logger.error(f"Failed to detect system info: {e}")
            return None