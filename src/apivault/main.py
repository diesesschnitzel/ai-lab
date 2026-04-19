from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.apivault.config import settings
from src.apivault.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router, prefix="/api", tags=["health"])

    return app


app = create_app()
