import logging
from typing import Dict, Optional, List
from aistack.detectors.base import (
    GPUDetector,
   
)
from aistack.detectors.nvidia_smi.nvidia_smi import NvidiaSMI
from aistack.schemas.workers import SystemInfo,  GPUDevicesInfo
from aistack.detectors.fastfetch.fastfetch import Fastfetch
from aistack.detectors.npu_smi.npu_smi import NPUSMI
from aistack.detectors.rocm_smi.rocm_smi import RocmSMI
from aistack.detectors.regredit.regredit import Regredit
from aistack.utils import platform


logger = logging.getLogger(__name__)


class DetectorFactory:
    def __init__(
        self,
        device: Optional[str] = None,
        gpu_detectors: Optional[Dict[str, List[GPUDetector]]] = None,
        system_info_detector: Optional[SystemInfo] = None,
    ):
        logger.info("Initializing DetectorFactory...")
        self.system_info_detector = system_info_detector or Fastfetch()
        logger.info(f"System info detector: {self.system_info_detector.__class__.__name__}")
        
        self.device = device if device else platform.device()
        logger.info(f"Detected device type: {self.device}")
        
        if self.device:
            all_gpu_detectors = gpu_detectors or self._get_builtin_gpu_detectors()
            self.gpu_detectors = all_gpu_detectors.get(self.device)
            logger.info(f"GPU detectors for {self.device}: {len(self.gpu_detectors) if self.gpu_detectors else 0} detectors")
        else:
            logger.warning("No specific device type detected, will use fastfetch as fallback")
            # 如果没有检测到特定设备类型，使用fastfetch作为通用检测器
            fastfetch = Fastfetch()
            self.gpu_detectors = [fastfetch] if fastfetch.is_available() else []
            logger.info(f"Fallback GPU detectors: {len(self.gpu_detectors)} detectors")

        logger.info("Starting detector validation...")
        self._validate_detectors()
        logger.info("DetectorFactory initialization completed")

    def _get_builtin_gpu_detectors(self) -> Dict[str, GPUDetector]:
        logger.info("Creating builtin GPU detectors...")
        fastfetch = Fastfetch()
        detectors = {
            platform.DeviceTypeEnum.CUDA.value: [NvidiaSMI()],
            platform.DeviceTypeEnum.NPU.value: [NPUSMI()],
            platform.DeviceTypeEnum.MPS.value: [fastfetch],
            platform.DeviceTypeEnum.MUSA.value: [fastfetch],
            platform.DeviceTypeEnum.ROCM.value: [RocmSMI(), Regredit()],
            platform.DeviceTypeEnum.DCU.value: [RocmSMI()],
        }
        logger.info(f"Created detectors for device types: {list(detectors.keys())}")
        return detectors

    def _validate_detectors(self):
        if not self.system_info_detector.is_available():
            logger.warning(
                f"System info detector {self.system_info_detector.__class__.__name__} is not available, "
                "system info detection will be limited"
            )

        if self.device:
            if not self.gpu_detectors:
                logger.warning(f"GPU detectors for {self.device} not supported")
                return

            available = False
            for detector in self.gpu_detectors:
                if detector.is_available():
                    available = True

            if not available:
                logger.warning(f"No GPU detectors available for {self.device}")

    def detect_gpus(self) -> GPUDevicesInfo:
        logger.info(f"Starting GPU detection for device: {self.device}")
        if not self.device and not self.gpu_detectors:
            logger.warning("No device type detected and no fallback detectors available, returning empty GPU list")
            return []

        logger.info(f"Checking {len(self.gpu_detectors)} GPU detectors...")
        for i, detector in enumerate(self.gpu_detectors):
            logger.info(f"Testing detector {i}: {detector.__class__.__name__}")
            if detector.is_available():
                logger.info(f"Detector {detector.__class__.__name__} is available, gathering GPU info...")
                gpus = detector.gather_gpu_info()
                if gpus:
                    logger.info(f"Found {len(gpus)} GPU devices")
                    filtered_gpus = self._filter_gpu_devices(gpus)
                    logger.info(f"After filtering: {len(filtered_gpus)} GPU devices")
                    return filtered_gpus
                else:
                    logger.warning(f"Detector {detector.__class__.__name__} returned no GPU devices")
            else:
                logger.warning(f"Detector {detector.__class__.__name__} is not available")

        logger.warning("No GPU detectors returned valid results")
        return []

    def detect_system_info(self) -> SystemInfo:
        logger.info("Starting system info detection...")
        system_info = self.system_info_detector.gather_system_info()
        logger.info("System info detection completed")
        return system_info

    def _filter_gpu_devices(self, gpu_devices: GPUDevicesInfo) -> GPUDevicesInfo:
        # Ignore the device without memory.
        return [device for device in gpu_devices if device.memory.total > 0]
