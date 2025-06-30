from typing import Optional
from fastapi import APIRouter
from sqlmodel import select

from aistack.api.exceptions import (
    NotFoundException,
    InternalServerErrorException,
)
from aistack.server.deps import SessionDep
from aistack.schemas.preset_models import (
    PresetModelsResponse,
    PresetModelWithStatus,
    PresetModelDownloadRequest,
)
from aistack.schemas.model_files import ModelFile, ModelFileCreate
from aistack.utils.preset_models import preset_models_service

router = APIRouter()


@router.get("", response_model=PresetModelsResponse)
async def get_preset_models(
    session: SessionDep,
    category: Optional[str] = None,
    search: Optional[str] = None,
    recommended_only: Optional[bool] = None,
):
    """获取预设模型列表，包含下载状态"""
    try:
        # 步骤 1: 根据分类或搜索词获取基础模型列表
        if category:
            preset_models = preset_models_service.get_preset_models_by_category(category)
        elif search:
            preset_models = preset_models_service.search_models(search)
        else:
            preset_models = preset_models_service.load_preset_models()
        
        # 步骤 2: 如果指定了 recommended_only，则对列表进行过滤
        if recommended_only is True:
            preset_models = [model for model in preset_models if model.recommended]
        elif recommended_only is False:
            preset_models = [model for model in preset_models if not model.recommended]

        # 查询数据库中已下载的预设模型
        downloaded_models_query = select(ModelFile).where(
            ModelFile.is_preset_model == True
        )
        downloaded_models = (await session.exec(downloaded_models_query)).all()
        
        # 创建预设模型ID到下载状态的映射
        downloaded_map = {}
        for model_file in downloaded_models:
            if model_file.preset_model_id:
                downloaded_map[model_file.preset_model_id] = {
                    'is_downloaded': True,
                    'model_file_id': model_file.id,
                    'download_progress': model_file.download_progress,
                    'state': model_file.state.value if model_file.state else None,
                    'created_at': model_file.created_at,
                }
        
        # 构建响应数据
        models_with_status = []
        for preset_model in preset_models:
            download_status = downloaded_map.get(preset_model.id, {
                'is_downloaded': False,
                'model_file_id': None,
                'download_progress': None,
                'state': None,
                'created_at': None,
            })
            
            model_with_status = PresetModelWithStatus(
                **preset_model.model_dump(),
                **download_status
            )
            models_with_status.append(model_with_status)
        
        # 获取所有分类
        categories = preset_models_service.get_all_categories()
        
        return PresetModelsResponse(
            models=models_with_status,
            total=len(models_with_status),
            categories=categories
        )
        
    except Exception as e:
        raise InternalServerErrorException(message=f"获取预设模型列表失败: {str(e)}")


@router.post("/download", response_model=dict)
async def download_preset_model(
    session: SessionDep,
    download_request: PresetModelDownloadRequest,
):
    """下载预设模型"""
    try:
        preset_model_id = download_request.preset_model_id
        # 获取预设模型信息
        preset_model = preset_models_service.get_preset_model_by_id(preset_model_id)
        if not preset_model:
            raise NotFoundException(message=f"预设模型 {preset_model_id} 不存在")
        
        # 检查是否已经下载过
        existing_model_query = select(ModelFile).where(
            ModelFile.is_preset_model == True,
            ModelFile.preset_model_id == preset_model_id
        )
        existing_model = (await session.exec(existing_model_query)).first()
        
        if existing_model:
            return {
                "message": "该预设模型已经下载过",
                "model_file_id": existing_model.id,
                "state": existing_model.state.value if existing_model.state else None
            }
        
        # 创建模型文件记录
        model_file_data = {
            "source": preset_model.source,
            "size": preset_model.size,
            "worker_id": download_request.worker_id,
            "local_dir": download_request.local_dir,
            "cleanup_on_delete": download_request.cleanup_on_delete,
            "is_preset_model": True,
            "preset_model_id": preset_model.id,
            "preset_model_name": preset_model.name,
            "preset_model_description": preset_model.description,
            "preset_model_category": preset_model.category,
            "preset_model_tags": preset_model.tags,
            "preset_model_recommended": preset_model.recommended,
        }
        
        # 根据源类型添加相应字段
        if preset_model.source.value == "HUGGING_FACE":
            model_file_data.update({
                "huggingface_repo_id": preset_model.huggingface_repo_id,
                "huggingface_filename": preset_model.huggingface_filename,
            })
        elif preset_model.source.value == "OLLAMA_LIBRARY":
            model_file_data.update({
                "ollama_library_model_name": preset_model.ollama_library_model_name,
            })
        elif preset_model.source.value == "MODEL_SCOPE":
            model_file_data.update({
                "model_scope_model_id": preset_model.model_scope_model_id,
                "model_scope_file_path": preset_model.model_scope_file_path,
            })
        elif preset_model.source.value == "LOCAL_PATH":
            model_file_data.update({
                "local_path": preset_model.local_path,
            })
        
        # 创建模型文件
        model_file = ModelFile(**model_file_data)
        model_file = await ModelFile.create(session, model_file)
        
        return {
            "message": "预设模型下载任务已创建",
            "model_file_id": model_file.id,
            "preset_model_id": preset_model_id,
            "state": model_file.state.value
        }
        
    except Exception as e:
        raise InternalServerErrorException(message=f"下载预设模型失败: {str(e)}")


#@router.get("/categories", response_model=list[str])
async def get_preset_model_categories():
    """获取所有预设模型分类"""
    try:
        return preset_models_service.get_all_categories()
    except Exception as e:
        raise InternalServerErrorException(message=f"获取预设模型分类失败: {str(e)}") 