from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from aistack.schemas.workers import GPUDevicesInfo, GPUDeviceInfo  # 从workers.py导入
from aistack.collector import GPUResourceCollector
from aistack.api.exceptions import NotFoundException

router = APIRouter()

@router.get("", response_model=dict)  # 简化返回类型
async def get_gpus(search: Optional[str] = None, page: int = 1, per_page: int = 20):
    """获取所有GPU设备信息"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"API call: get_gpus (search={search}, page={page}, per_page={per_page})")
    
    collector = GPUResourceCollector()
    gpu_devices = collector.collect_gpu_resources()
    
    # 简单的搜索过滤
    if search:
        gpu_devices = [gpu for gpu in gpu_devices if search.lower() in gpu.name.lower()]
    
    # 简单的分页
    total = len(gpu_devices)
    start = (page - 1) * per_page
    end = start + per_page
    items = gpu_devices[start:end]
    
    return {
        "items": [item.dict() for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.get("/system")
async def get_system_info():
    """获取系统信息"""
    collector = GPUResourceCollector()
    system_info = collector.collect_system_info()
    return system_info.dict() if system_info else None

@router.get("/health")
async def get_gpu_health():
    """获取GPU健康状态"""
    collector = GPUResourceCollector()
    gpu_devices = collector.collect_gpu_resources()
    
    health_info = {
        "total_gpus": len(gpu_devices),
        "gpu_types": list(set(gpu.type for gpu in gpu_devices if gpu.type)),
        "vendors": list(set(gpu.vendor for gpu in gpu_devices if gpu.vendor)),
        "status": "healthy" if gpu_devices else "no_gpus_detected"
    }
    
    return health_info