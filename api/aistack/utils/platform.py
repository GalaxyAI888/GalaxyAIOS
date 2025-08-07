from enum import Enum
import os
import platform
import logging
import threading
import re
import subprocess

from aistack.utils.command import is_command_available
from aistack.schemas.workers import VendorEnum

logger = logging.getLogger(__name__)


def system() -> str:
    return platform.uname().system.lower()


def get_native_arch() -> str:
    system = platform.system()
    if system == "Windows":
        import pythoncom

        if threading.current_thread() is not threading.main_thread():
            pythoncom.CoInitialize()

        # Windows emulation will mask the native architecture
        # https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation
        try:
            import wmi

            c = wmi.WMI()
            processor_info = c.Win32_Processor()
            arch_num = processor_info[0].Architecture

            # https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-processor
            arch_map = {
                0: 'x86',
                1: 'MIPS',
                2: 'Alpha',
                3: 'PowerPC',
                5: 'ARM',
                6: 'ia64',
                9: 'AMD64',
                12: 'ARM64',
            }

            arch = arch_map.get(arch_num, 'unknown')
            if arch != 'unknown':
                return arch.lower()
        except Exception as e:
            logger.warning(f"Failed to get native architecture from WMI, {e}")
        finally:
            if threading.current_thread() is not threading.main_thread():
                pythoncom.CoUninitialize()

    return platform.machine().lower()


def arch() -> str:
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "i386": "386",
        "i686": "386",
        "arm64": "arm64",
        "aarch64": "arm64",
        "armv7l": "arm",
        "arm": "arm",
        "ppc64le": "ppc64le",
        "s390x": "s390x",
        "x86": "x86",
        "mips": "mips",
        "alpha": "alpha",
        "powerpc": "powerpc",
        "ia64": "ia64",
    }
    return arch_map.get(get_native_arch(), "unknown")


class DeviceTypeEnum(str, Enum):
    CUDA = "cuda"
    NPU = "npu"
    MPS = "mps"
    ROCM = "rocm"
    MUSA = "musa"
    DCU = "dcu"  


def device() -> str:
    """
    Returns the customized device type. This is similar to the device types in PyTorch but includes some additional types. Examples include:
    - cuda
    - musa
    - npu
    - mps
    - rocm
    - etc.
    """
    logger.info("Starting device type detection...")
    
    # Check CUDA
    nvidia_smi_available = is_command_available("nvidia-smi")
    cuda_path_linux = os.path.exists("/usr/local/cuda")
    cuda_path_windows = os.path.exists("C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA")
    
    logger.info(f"CUDA detection: nvidia-smi={nvidia_smi_available}, cuda_path_linux={cuda_path_linux}, cuda_path_windows={cuda_path_windows}")
    
    if nvidia_smi_available or cuda_path_linux or cuda_path_windows:
        logger.info("CUDA device detected")
        return DeviceTypeEnum.CUDA.value

    # Check MUSA
    mthreads_gmi_available = is_command_available("mthreads-gmi")
    musa_path_linux = os.path.exists("/usr/local/musa")
    musa_path_opt = os.path.exists("/opt/musa")
    
    logger.info(f"MUSA detection: mthreads-gmi={mthreads_gmi_available}, musa_path_linux={musa_path_linux}, musa_path_opt={musa_path_opt}")
    
    if mthreads_gmi_available or musa_path_linux or musa_path_opt:
        logger.info("MUSA device detected")
        return DeviceTypeEnum.MUSA.value

    # Check NPU
    npu_smi_available = is_command_available("npu-smi")
    logger.info(f"NPU detection: npu-smi={npu_smi_available}")
    if npu_smi_available:
        logger.info("NPU device detected")
        return "npu"
    
    # Check DCU
    hy_smi_available = is_command_available("hy-smi")
    logger.info(f"DCU detection: hy-smi={hy_smi_available}")
    if hy_smi_available:
        logger.info("DCU device detected")
        return "dcu"  

    # Check MPS (Apple Silicon)
    current_system = system()
    current_arch = arch()
    logger.info(f"MPS detection: system={current_system}, arch={current_arch}")
    if current_system == "darwin" and current_arch == "arm64":
        logger.info("MPS device detected")
        return DeviceTypeEnum.MPS.value

    # Check ROCm
    rocm_smi_available = is_command_available("rocm-smi")
    rocm_path_windows = os.path.exists("C:\\Program Files\\AMD\\ROCm")
    logger.info(f"ROCM detection: rocm-smi={rocm_smi_available}, rocm_path_windows={rocm_path_windows}")
    if rocm_smi_available or rocm_path_windows:
        logger.info("ROCM device detected")
        return DeviceTypeEnum.ROCM.value
    
    logger.warning("No GPU device type detected")
    return ""


def device_type_from_vendor(vendor: VendorEnum) -> str:
    mapping = {
        VendorEnum.NVIDIA.value: DeviceTypeEnum.CUDA.value,
        VendorEnum.Huawei.value: DeviceTypeEnum.NPU.value,
        VendorEnum.Apple.value: DeviceTypeEnum.MPS.value,
        VendorEnum.AMD.value: DeviceTypeEnum.ROCM.value,
        VendorEnum.Hygon.value: DeviceTypeEnum.DCU.value,  
        VendorEnum.MTHREADS.value: DeviceTypeEnum.MUSA.value,
    }

    return mapping.get(vendor, "")
# 在现有platform.py文件末尾添加以下函数

def get_cuda_version() -> str:
    """
    Returns the CUDA toolkit version installed on the system.
    """
    if os.environ.get("CUDA_VERSION"):
        return os.environ["CUDA_VERSION"]

    try:
        import torch
        if torch.cuda.is_available():
            return torch.version.cuda
    except ImportError:
        pass

    if is_command_available("nvcc"):
        try:
            output = subprocess.check_output(["nvcc", "--version"], encoding="utf-8")
            match = re.search(r"release (\d+\.\d+),", output)
            if match:
                return match.group(1)
        except Exception as e:
            logger.error(f"Error running nvcc: {e}")
    return ""

def get_cann_version() -> str:
    """
    Returns the CANN version installed on the system.
    """
    env_cann_version = os.getenv("CANN_VERSION", "")
    if env_cann_version:
        return env_cann_version

    try:
        import torch  
        import torch_npu  
        from torch_npu.utils.collect_env import (
            get_cann_version as get_cann_version_from_env,
        )
        from torch_npu.npu.utils import get_cann_version

        cann_version = get_cann_version_from_env()
        if cann_version:
            return cann_version.lower()
        cann_version = get_cann_version()
        if cann_version:
            return cann_version.lower()
    except ImportError:
        pass

    return ""

def get_cann_chip() -> str:
    """
    Returns the CANN chip version installed on the system.
    """
    return os.getenv("CANN_CHIP", "")