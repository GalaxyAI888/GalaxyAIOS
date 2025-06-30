from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from aistack.schemas.models import SourceEnum


class PresetModelInfo(BaseModel):
    """预设模型信息"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: str
    name: str
    description: str
    category: str
    source: SourceEnum
    size: int
    tags: List[str]
    recommended: bool
    
    # 下载参数
    huggingface_repo_id: Optional[str] = None
    huggingface_filename: Optional[str] = None
    ollama_library_model_name: Optional[str] = None
    model_scope_model_id: Optional[str] = None
    model_scope_file_path: Optional[str] = None
    local_path: Optional[str] = None


class PresetModelWithStatus(PresetModelInfo):
    """包含下载状态的预设模型信息"""
    is_downloaded: bool = False
    model_file_id: Optional[int] = None
    download_progress: Optional[float] = None
    state: Optional[str] = None
    created_at: Optional[datetime] = None


class PresetModelsResponse(BaseModel):
    """预设模型列表响应"""
    model_config = ConfigDict(protected_namespaces=())
    
    models: List[PresetModelWithStatus]
    total: int
    categories: List[str]  # 所有可用的分类


class PresetModelDownloadRequest(BaseModel):
    """下载预设模型的请求"""
    model_config = ConfigDict(protected_namespaces=())
    
    preset_model_id: str
    worker_id: Optional[int] = None
    local_dir: Optional[str] = None
    cleanup_on_delete: Optional[bool] = True 