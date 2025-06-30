# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from aistack.api.exceptions import error_responses
from aistack.api import users
from aistack.task.aigc.routers import aigc_router
from aistack.api.model_file_routes import router as model_file_router
from aistack.api.preset_model_routes import router as preset_model_router



api_router = APIRouter(responses=error_responses)

v_router = APIRouter()


api_router.include_router(users.router, tags=["users"], prefix="/users")
v_router.include_router(aigc_router, tags=["task"], prefix="/aigc")
v_router.include_router(model_file_router, tags=["Model Files"],prefix="/model-files")
v_router.include_router(preset_model_router, tags=["Preset Models"], prefix="/preset-models")


api_router.include_router(
    v_router,  prefix="/v1"
)




