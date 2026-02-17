from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.database.engine import dispose_engine
from src.errors import PermanentError, QualityError, TransientError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: cleanup database engine on shutdown."""
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoDoc ADK Documentation Generator API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Exception handlers
    @app.exception_handler(TransientError)
    async def transient_error_handler(
        request: Request, exc: TransientError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(PermanentError)
    async def permanent_error_handler(
        request: Request, exc: PermanentError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(QualityError)
    async def quality_error_handler(
        request: Request, exc: QualityError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    # Routers (added as they are implemented)
    from src.api.routes.health import router as health_router
    from src.api.routes.jobs import router as jobs_router
    from src.api.routes.repositories import router as repositories_router

    app.include_router(health_router)
    app.include_router(repositories_router)
    app.include_router(jobs_router)
    from src.api.routes.documents import router as documents_router
    app.include_router(documents_router)
    # app.include_router(search_router)
    # app.include_router(webhooks_router)

    return app
