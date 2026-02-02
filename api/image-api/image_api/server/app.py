"""FastAPI application for Image API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from image_api import __version__
from .routers import router


app = FastAPI(
    title="Image API",
    description="A text-to-image and image-to-image server compatible with the OpenAI API",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Handle startup event."""
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown event."""
    from .model import get_model_instance

    instance = get_model_instance()
    if instance:
        instance.shutdown()
