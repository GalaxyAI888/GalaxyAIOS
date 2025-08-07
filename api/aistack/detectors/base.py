from abc import ABC, abstractmethod

from aistack.schemas.workers import SystemInfo, GPUDevicesInfo


class GPUDetector(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def gather_gpu_info(self) -> GPUDevicesInfo:
        pass


class SystemInfoDetector(ABC):
    @abstractmethod
    def gather_system_info(self) -> SystemInfo:
        pass
