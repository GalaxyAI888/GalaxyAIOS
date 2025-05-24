# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_cdn_host import monkey_patch_for_docs_ui
import httpx

from aistack.api.routes import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="AIStack",
    description="AIStack is a platform for running machine learning models.",
    version="0.1.0",
    lifespan=lifespan,
)
monkey_patch_for_docs_ui(app)
app.include_router(api_router)