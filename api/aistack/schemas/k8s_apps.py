from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, ConfigDict, model_validator, field_validator
from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, Relationship, SQLModel
import json

from aistack.schemas.common import UTCDateTime, pydantic_column_type
from aistack.mixins import BaseModelMixin


class K8sAppStatusEnum(str, Enum):
    """K8s应用状态枚举"""
    STOPPED = "stopped"
    DEPLOYING = "deploying"
    RUNNING = "running"
    ERROR = "error"
    UPDATING = "updating"
    SCALING = "scaling"
    DELETING = "deleting"


class K8sAppTypeEnum(str, Enum):
    """K8s应用类型枚举"""
    WEB_APP = "web_app"
    API_SERVICE = "api_service"
    MICROSERVICE = "microservice"
    WORKLOAD = "workload"


class K8sAppBase(SQLModel):
    """K8s应用基础模型"""
    name: str = Field(index=True, unique=True, description="应用名称")
    display_name: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="显示名称（如果未提供则使用name）"
    )
    description: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True), description="应用描述"
    )
    version: str = Field(default="1.0.0", description="版本")
    icon: Optional[str] = Field(default=None, description="应用图标URL")
    
    # 用户关联
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", description="创建者用户ID")
    
    # Docker镜像相关
    dockerfile: Optional[str] = Field(default=None, description="Dockerfile URL")
    docker_img_url: Optional[str] = Field(
        default=None, 
        alias="docker-img-url",
        description="Docker镜像URL"
    )
    img_name: Optional[str] = Field(
        default=None, 
        alias="img-name",
        description="镜像名称"
    )
    img_tag: str = Field(
        default="latest", 
        alias="img-tag",
        description="镜像标签"
    )
    imgsize: Optional[str] = Field(default=None, description="镜像大小")
    
    # K8s配置 - 接受对象或JSON字符串，自动转换为JSON字符串存储
    deployment: Optional[Union[Dict[str, Any], str]] = Field(
        sa_column=Column(Text), default=None, description="Deployment配置（对象或JSON字符串）"
    )
    service: Optional[Union[Dict[str, Any], str]] = Field(
        sa_column=Column(Text), default=None, description="Service配置（对象或JSON字符串）"
    )
    configmap: Optional[Union[Dict[str, Any], str]] = Field(
        sa_column=Column(Text), default=None, description="ConfigMap配置（对象或JSON字符串）"
    )
    ingress: Optional[Union[Dict[str, Any], str]] = Field(
        sa_column=Column(Text), default=None, description="Ingress配置（对象或JSON字符串）"
    )
    
    # 应用类型和分类
    app_type: K8sAppTypeEnum = Field(default=K8sAppTypeEnum.WEB_APP, description="应用类型")
    category: Optional[str] = Field(default=None, description="分类")
    tags: Optional[List[str]] = Field(
        sa_column=Column(JSON), default=[], description="标签"
    )
    
    # 状态
    status: K8sAppStatusEnum = Field(default=K8sAppStatusEnum.STOPPED, description="应用状态")
    is_active: bool = Field(default=True, description="是否激活")
    is_preset: bool = Field(default=False, description="是否预设应用")
    
    # 部署相关
    namespace: str = Field(default="default", description="K8s命名空间")
    replicas: int = Field(default=1, description="副本数量")
    
    # 状态消息
    status_message: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True), description="状态消息"
    )
    
    # 部署时间
    deployed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="部署时间"
    )
    last_updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(UTCDateTime), description="最后更新时间"
    )

    @model_validator(mode='before')
    @classmethod
    def set_display_name_before(cls, data: Any):
        """在验证前设置display_name默认值并处理字段别名"""
        # 字段别名处理 - 将连字符格式映射到下划线格式
        alias_mapping = {
            'docker-img-url': 'docker_img_url',
            'img-name': 'img_name', 
            'img-tag': 'img_tag'
        }
        
        if isinstance(data, dict):
            # 处理字段别名
            for alias, field_name in alias_mapping.items():
                if alias in data and field_name not in data:
                    data[field_name] = data.pop(alias)
            
            # 如果没有提供display_name，则使用name的值
            if 'display_name' not in data or data.get('display_name') is None:
                if 'name' in data:
                    data['display_name'] = data['name']
            # 如果是空字符串，也使用name的值
            elif isinstance(data.get('display_name'), str) and data['display_name'].strip() == "":
                if 'name' in data:
                    data['display_name'] = data['name']
        return data
    
    @model_validator(mode='after')
    def set_display_name_after(self):
        """如果display_name为空，则使用name作为默认值"""
        if not self.display_name:
            self.display_name = self.name
        return self

    @field_validator('deployment', 'service', 'configmap', 'ingress', mode='before')
    @classmethod
    def convert_to_json_string(cls, v):
        """将对象自动转换为JSON字符串"""
        if v is None:
            return None
        if isinstance(v, str):
            # 如果已经是字符串，验证是否为有效JSON
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                # 如果不是有效JSON，当作普通字符串处理
                return v
        elif isinstance(v, dict):
            # 如果是字典，转换为JSON字符串
            return json.dumps(v, ensure_ascii=False)
        else:
            # 其他类型尝试转换为JSON
            try:
                return json.dumps(v, ensure_ascii=False)
            except (TypeError, ValueError):
                raise ValueError(f"无法将 {type(v)} 转换为JSON字符串")


class K8sApp(K8sAppBase, BaseModelMixin, table=True):
    """K8s应用数据库模型"""
    __tablename__ = 'k8s_apps'
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联用户
    user: Optional["User"] = Relationship(back_populates="k8s_apps")
    
    # 关联实例
    instances: List["K8sAppInstance"] = Relationship(back_populates="k8s_app")


class K8sAppCreate(K8sAppBase):
    """创建K8s应用请求模型"""
    model_config = ConfigDict(
        populate_by_name=True,  # 允许同时使用字段名和别名
        populate_by_alias=True  # 允许使用别名
    )


class K8sAppUpdate(BaseModel):
    """更新K8s应用请求模型"""
    model_config = ConfigDict(
        populate_by_name=True,  # 允许同时使用字段名和别名
        populate_by_alias=True  # 允许使用别名
    )
    
    display_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    icon: Optional[str] = None
    dockerfile: Optional[str] = None
    docker_img_url: Optional[str] = Field(default=None, alias="docker-img-url")
    img_name: Optional[str] = Field(default=None, alias="img-name")
    img_tag: Optional[str] = Field(default=None, alias="img-tag")
    imgsize: Optional[str] = None
    deployment: Optional[Union[Dict[str, Any], str]] = None
    service: Optional[Union[Dict[str, Any], str]] = None
    configmap: Optional[Union[Dict[str, Any], str]] = None
    ingress: Optional[Union[Dict[str, Any], str]] = None
    app_type: Optional[K8sAppTypeEnum] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    namespace: Optional[str] = None
    replicas: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator('deployment', 'service', 'configmap', 'ingress', mode='before')
    @classmethod
    def convert_to_json_string(cls, v):
        """将对象自动转换为JSON字符串"""
        if v is None:
            return None
        if isinstance(v, str):
            # 如果已经是字符串，验证是否为有效JSON
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                # 如果不是有效JSON，当作普通字符串处理
                return v
        elif isinstance(v, dict):
            # 如果是字典，转换为JSON字符串
            return json.dumps(v, ensure_ascii=False)
        else:
            # 其他类型尝试转换为JSON
            try:
                return json.dumps(v, ensure_ascii=False)
            except (TypeError, ValueError):
                raise ValueError(f"无法将 {type(v)} 转换为JSON字符串")


class K8sAppPublic(K8sAppBase):
    """K8s应用公开响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime


class K8sAppInstanceBase(SQLModel):
    """K8s应用实例基础模型"""
    k8s_app_id: int = Field(foreign_key="k8s_apps.id", description="关联的K8s应用ID")
    pod_name: Optional[str] = Field(default=None, description="Pod名称")
    status: K8sAppStatusEnum = Field(default=K8sAppStatusEnum.STOPPED, description="实例状态")
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
    
    # 网络信息
    pod_ip: Optional[str] = Field(default=None, description="Pod IP地址")
    node_name: Optional[str] = Field(default=None, description="节点名称")
    
    # K8s资源信息
    deployment_name: Optional[str] = Field(default=None, description="Deployment名称")
    service_name: Optional[str] = Field(default=None, description="Service名称")
    namespace: Optional[str] = Field(default=None, description="命名空间")


class K8sAppInstance(K8sAppInstanceBase, BaseModelMixin, table=True):
    """K8s应用实例数据库模型"""
    __tablename__ = 'k8s_app_instances'
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联K8s应用
    k8s_app: Optional[K8sApp] = Relationship(back_populates="instances")


class K8sAppInstanceCreate(K8sAppInstanceBase):
    """创建K8s应用实例请求模型"""
    pass


class K8sAppInstanceUpdate(BaseModel):
    """更新K8s应用实例请求模型"""
    pod_name: Optional[str] = None
    status: Optional[K8sAppStatusEnum] = None
    status_message: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    memory_usage: Optional[str] = None
    cpu_usage: Optional[float] = None
    pod_ip: Optional[str] = None
    node_name: Optional[str] = None
    deployment_name: Optional[str] = None
    service_name: Optional[str] = None
    namespace: Optional[str] = None


class K8sAppInstancePublic(K8sAppInstanceBase):
    """K8s应用实例公开响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    k8s_app: K8sAppPublic


# 为K8sApp添加关联
K8sApp.model_rebuild()
K8sAppInstance.model_rebuild()