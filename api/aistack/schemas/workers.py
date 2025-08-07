# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, List
from pydantic import ConfigDict, BaseModel, Field
from sqlmodel import SQLModel, JSON, Column, Text

from aistack.mixins import BaseModelMixin
from aistack.schemas.common import PaginatedList, UTCDateTime, pydantic_column_type
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class VendorEnum(str, Enum):
    NVIDIA = "NVIDIA"
    MTHREADS = "Moore Threads"
    Apple = "Apple"
    Huawei = "Huawei"
    AMD = "AMD"
    Hygon = "Hygon"
class RPCServer(BaseModel):
    pid: Optional[int] = None
    port: Optional[int] = None
    gpu_index: Optional[int] = None







class UtilizationInfo(BaseModel):
    total: int = Field(default=None)
    utilization_rate: Optional[float] = Field(default=None)  # range from 0 to 100


class MemoryInfo(UtilizationInfo):
    is_unified_memory: bool = Field(default=False)
    used: Optional[int] = Field(default=None)
    allocated: Optional[int] = Field(default=None)


class CPUInfo(UtilizationInfo):
    pass


class GPUCoreInfo(UtilizationInfo):
    pass


class GPUNetworkInfo(BaseModel):
    status: str = Field(default="up")  # Network status (up/down)
    inet: str = Field(default="")  # IPv4 address
    netmask: str = Field(default="")  # Subnet mask
    mac: str = Field(default="")  # MAC address
    gateway: str = Field(default="")  # Default gateway
    iface: Optional[str] = Field(default=None)  # Network interface name
    mtu: Optional[int] = Field(default=None)  # Maximum Transmission Unit


class SwapInfo(UtilizationInfo):
    used: Optional[int] = Field(default=None)
    pass


class GPUDeviceInfo(BaseModel):
    # GPU index, which is the logic ID of the GPU chip,
    # which is a human-readable index and counted from 0 generally.
    # It might be recognized as the GPU device ID in some cases, when there is no more than one GPU chip on the same card.
    index: Optional[int] = Field(default=None)
    # GPU device index, which is the index of the onboard GPU device.
    # In Linux, it can be retrieved under the /dev/ path.
    # For example, /dev/nvidia0 (the first Nvidia card), /dev/davinci2(the third Ascend card), etc.
    device_index: Optional[int] = Field(default=0)
    # GPU device chip index, which is the index of the GPU chip on the card.
    # It works with `device_index` to identify a GPU chip uniquely.
    # For example, the first chip on the first card is 0, and the second chip on the first card is 1.
    device_chip_index: Optional[int] = Field(default=0)
    name: str = Field(default="")
    uuid: Optional[str] = Field(default="")
    vendor: Optional[str] = Field(default="")
    core: Optional[GPUCoreInfo] = Field(sa_column=Column(JSON), default=None)
    memory: Optional[MemoryInfo] = Field(sa_column=Column(JSON), default=None)
    network: Optional[GPUNetworkInfo] = Field(sa_column=Column(JSON), default=None)
    temperature: Optional[float] = Field(default=None)  # in celsius
    labels: Dict[str, str] = Field(sa_column=Column(JSON), default={})
    type: Optional[str] = Field(default="")


GPUDevicesInfo = List[GPUDeviceInfo]





class MountPoint(BaseModel):
    name: str = Field(default="")
    mount_point: str = Field(default="")
    mount_from: str = Field(default="")
    total: int = Field(default=None)  # in bytes
    used: Optional[int] = Field(default=None)
    free: Optional[int] = Field(default=None)
    available: Optional[int] = Field(default=None)


FileSystemInfo = List[MountPoint]


class OperatingSystemInfo(BaseModel):
    name: str = Field(default="")
    version: str = Field(default="")


class KernelInfo(BaseModel):
    name: str = Field(default="")
    release: str = Field(default="")
    version: str = Field(default="")
    architecture: str = Field(default="")


class UptimeInfo(BaseModel):
    uptime: float = Field(default=None)  # in seconds
    boot_time: str = Field(default="")


class SystemReserved(BaseModel):
    ram: Optional[int] = Field(default=None)
    vram: Optional[int] = Field(default=None)



class SystemInfo(BaseModel):
    cpu: Optional[CPUInfo] = Field(sa_column=Column(JSON), default=None)
    memory: Optional[MemoryInfo] = Field(sa_column=Column(JSON), default=None)
    swap: Optional[SwapInfo] = Field(sa_column=Column(JSON), default=None)
    filesystem: Optional[FileSystemInfo] = Field(sa_column=Column(JSON), default=None)
    os: Optional[OperatingSystemInfo] = Field(sa_column=Column(JSON), default=None)
    kernel: Optional[KernelInfo] = Field(sa_column=Column(JSON), default=None)
    uptime: Optional[UptimeInfo] = Field(sa_column=Column(JSON), default=None)





