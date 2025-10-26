# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from aistack.api.exceptions import error_responses
from aistack.api import users
from aistack.task.aigc.routers import aigc_router
from aistack.api.model_file_routes import router as model_file_router
from aistack.api.preset_model_routes import router as preset_model_router
from aistack.api.app_routes import router as app_router
from aistack.api.k8s_app_routes import router as k8s_app_router
from aistack.api.file_routes import router as file_router

from aistack.api.gpu_routes import router as gpu_router
from aistack.api.image_routes import router as image_router



api_router = APIRouter(responses=error_responses)

v_router = APIRouter()


api_router.include_router(users.router, tags=["users"], prefix="/users")
v_router.include_router(aigc_router, tags=["task"], prefix="/aigc")
v_router.include_router(model_file_router, tags=["Model Files"],prefix="/model-files")
v_router.include_router(preset_model_router, tags=["Preset Models"], prefix="/preset-models")
# v_router.include_router(app_router, tags=["应用管理"], prefix="/apps")  # 已屏蔽Docker应用管理，改用K8s
v_router.include_router(k8s_app_router, tags=["K8s应用管理"], prefix="/k8s-apps")
v_router.include_router(file_router, tags=["文件管理"], prefix="/files")
v_router.include_router(gpu_router, tags=["GPU监控"], prefix="/gpu")
v_router.include_router(image_router, tags=["镜像管理"])


api_router.include_router(
    v_router,  prefix="/v1"
)




