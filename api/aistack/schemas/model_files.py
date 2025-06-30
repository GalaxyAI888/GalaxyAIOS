from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import JSON, BigInteger, Column, Field, Relationship, SQLModel, Text

from aistack.mixins import BaseModelMixin
from aistack.schemas.common import PaginatedList
from aistack.schemas.links import ModelInstanceModelFileLink
from aistack.schemas.models import ModelSource, ModelInstance


class ModelFileStateEnum(str, Enum):
    ERROR = "error"
    DOWNLOADING = "downloading"
    READY = "ready"


class ModelFileBase(SQLModel, ModelSource):
    local_dir: Optional[str] = None
    worker_id: Optional[int] = None
    cleanup_on_delete: Optional[bool] = None

    size: Optional[int] = Field(sa_column=Column(BigInteger), default=None)
    download_progress: Optional[float] = None
    resolved_paths: List[str] = Field(sa_column=Column(JSON), default=[])
    state: ModelFileStateEnum = ModelFileStateEnum.DOWNLOADING
    state_message: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    
    # 预设模型相关字段
    is_preset_model: bool = Field(default=False, index=True)  # 是否为预设模型
    preset_model_id: Optional[str] = Field(default=None, index=True)  # 预设模型ID
    preset_model_name: Optional[str] = Field(default=None)  # 预设模型名称
    preset_model_description: Optional[str] = Field(default=None)  # 预设模型描述
    preset_model_category: Optional[str] = Field(default=None)  # 预设模型分类
    preset_model_tags: Optional[List[str]] = Field(sa_column=Column(JSON), default=None)  # 预设模型标签
    preset_model_recommended: Optional[bool] = Field(default=False)  # 是否为推荐模型


class ModelFile(ModelFileBase, BaseModelMixin, table=True):
    __tablename__ = 'model_files'
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique index of the model source
    source_index: Optional[str] = Field(index=True, unique=True, default=None)

    instances: list[ModelInstance] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"},
        back_populates="model_files",
        link_model=ModelInstanceModelFileLink,
    )


class ModelFileCreate(ModelFileBase):
    pass


class ModelFileUpdate(ModelFileBase):
    pass


class ModelFilePublic(
    ModelFileBase,
):
    id: int
    created_at: datetime
    updated_at: datetime


ModelFilesPublic = PaginatedList[ModelFilePublic]
