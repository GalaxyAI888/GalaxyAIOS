from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, Relationship, SQLModel

from aistack.schemas.common import UTCDateTime, pydantic_column_type
from aistack.mixins import BaseModelMixin


class AppStatusEnum(str, Enum):
    """应用状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    BUILDING = "building"
    BUILD_FAILED = "build_failed"


class AppTypeEnum(str, Enum):
    """应用类型枚举"""
    WEB_APP = "web_app"
    API_SERVICE = "api_service"
    DESKTOP_APP = "desktop_app"
    UTILITY = "utility"


class ImageSourceEnum(str, Enum):
    """镜像获取方式枚举"""
    BUILD = "build"      # 通过Dockerfile构建
    PULL = "pull"        # 通过docker pull拉取


class AppVolume(BaseModel):
    """应用卷映射配置"""
    host_path: str = Field(description="主机路径")
    container_path: str = Field(description="容器内路径")
    read_only: bool = Field(default=False, description="是否只读")
    description: Optional[str] = Field(default=None, description="卷描述")

    model_config = ConfigDict(from_attributes=True)


class AppURL(BaseModel):
    """应用URL配置"""
    name: str = Field(description="URL名称")
    url: str = Field(description="完整URL")
    port: Optional[int] = Field(default=None, description="端口号")
    path: Optional[str] = Field(default=None, description="路径")
    description: Optional[str] = Field(default=None, description="URL描述")
    is_primary: bool = Field(default=False, description="是否为主要URL")

    model_config = ConfigDict(from_attributes=True)


class AppBase(SQLModel):
    """应用基础模型"""
    name: str = Field(index=True, unique=True, description="应用名称")
    display_name: str = Field(description="显示名称")
    description: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True), description="应用描述"
    )
    app_type: AppTypeEnum = Field(default=AppTypeEnum.WEB_APP, description="应用类型")
    
    # 用户关联
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", description="创建者用户ID")
    
    # Docker相关配置
    image_source: ImageSourceEnum = Field(default=ImageSourceEnum.BUILD, description="镜像获取方式")
    dockerfile_path: Optional[str] = Field(default=None, description="Dockerfile路径（构建时使用）")
    image_name: str = Field(description="Docker镜像名称")
    image_tag: str = Field(default="latest", description="Docker镜像标签")
    image_url: Optional[str] = Field(default=None, description="镜像完整地址（拉取时使用）")
    
    # 容器配置
    container_name: Optional[str] = Field(default=None, description="容器名称")
    ports: Optional[Dict[str, str]] = Field(
        sa_column=Column(JSON), default={}, description="端口映射 {容器端口: 主机端口}"
    )
    environment: Optional[Dict[str, str]] = Field(
        sa_column=Column(JSON), default={}, description="环境变量"
    )
    volumes: Optional[List[AppVolume]] = Field(
        sa_column=Column(JSON), default=[], description="卷映射"
    )
    urls: Optional[List[AppURL]] = Field(
        sa_column=Column(JSON), default=[], description="URL配置"
    )
    
    # 资源限制
    memory_limit: Optional[str] = Field(default=None, description="内存限制 (如: 512m)")
    cpu_limit: Optional[str] = Field(default=None, description="CPU限制 (如: 0.5)")
    
    # 元数据
    tags: Optional[List[str]] = Field(
        sa_column=Column(JSON), default=[], description="标签"
    )
    category: Optional[str] = Field(default=None, description="分类")
    version: Optional[str] = Field(default="1.0.0", description="版本")
    
    # 状态
    is_active: bool = Field(default=True, description="是否激活")
    is_preset: bool = Field(default=False, description="是否预设应用")
    
    # 状态字段
    status: AppStatusEnum = Field(default=AppStatusEnum.STOPPED, description="应用状态")
    
    # 构建相关字段
    build_status: Optional[str] = Field(default=None, description="构建状态")
    build_message: Optional[str] = Field(default=None, description="构建消息")
    build_started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="构建开始时间"
    )
    build_finished_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="构建完成时间"
    )


class App(AppBase, BaseModelMixin, table=True):
    """应用数据库模型"""
    __tablename__ = 'apps'
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联实例
    instances: List["AppInstance"] = Relationship(back_populates="app")
    
    # 关联用户
    user: Optional["User"] = Relationship(back_populates="apps")


class AppCreate(AppBase):
    """创建应用请求模型"""
    pass


class AppUpdate(BaseModel):
    """更新应用请求模型"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    app_type: Optional[AppTypeEnum] = None
    image_source: Optional[ImageSourceEnum] = None
    dockerfile_path: Optional[str] = None
    image_name: Optional[str] = None
    image_tag: Optional[str] = None
    image_url: Optional[str] = None
    container_name: Optional[str] = None
    ports: Optional[Dict[str, str]] = None
    environment: Optional[Dict[str, str]] = None
    volumes: Optional[List[AppVolume]] = None
    urls: Optional[List[AppURL]] = None
    memory_limit: Optional[str] = None
    cpu_limit: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None


class AppPublic(AppBase):
    """应用公开响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime


class AppInstanceBase(SQLModel):
    """应用实例基础模型"""
    app_id: int = Field(foreign_key="apps.id", description="关联的应用ID")
    container_id: Optional[str] = Field(default=None, description="Docker容器ID")
    status: AppStatusEnum = Field(default=AppStatusEnum.STOPPED, description="实例状态")
    status_message: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True), description="状态消息"
    )
    
    # 运行时信息
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="启动时间"
    )
    stopped_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="停止时间"
    )
    
    # 资源使用情况
    memory_usage: Optional[str] = Field(default=None, description="内存使用")
    cpu_usage: Optional[float] = Field(default=None, description="CPU使用率")
    
    # GPU使用情况
    gpu_info: Optional[List[Dict[str, Any]]] = Field(
        sa_column=Column(JSON), default=[], description="GPU使用信息"
    )
    
    # 网络信息
    ip_address: Optional[str] = Field(default=None, description="容器IP地址")
    exposed_ports: Optional[Dict[str, str]] = Field(
        sa_column=Column(JSON), default={}, description="暴露的端口"
    )


class AppInstance(AppInstanceBase, BaseModelMixin, table=True):
    """应用实例数据库模型"""
    __tablename__ = 'app_instances'
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联应用
    app: Optional[App] = Relationship(back_populates="instances")


class AppInstanceCreate(AppInstanceBase):
    """创建应用实例请求模型"""
    pass


class AppInstanceUpdate(BaseModel):
    """更新应用实例请求模型"""
    status: Optional[AppStatusEnum] = None
    status_message: Optional[str] = None
    container_id: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    memory_usage: Optional[str] = None
    cpu_usage: Optional[float] = None
    gpu_info: Optional[List[Dict[str, Any]]] = None
    ip_address: Optional[str] = None
    exposed_ports: Optional[Dict[str, str]] = None


class AppInstancePublic(AppInstanceBase):
    """应用实例公开响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    app: AppPublic 