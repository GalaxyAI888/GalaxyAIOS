# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from aistack.api.exceptions import error_responses
from aistack.api import users
from aistack.task.aigc.routers import aigc_router

api_router = APIRouter(responses=error_responses)
api_router.include_router(users.router, tags=["users"], prefix="/users")
api_router.include_router(aigc_router, tags=["task"], prefix="/aigc")



