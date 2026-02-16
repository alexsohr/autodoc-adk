from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.config.settings import get_settings

router = APIRouter(tags=["health"])


class DependencyHealth(BaseModel):
    status: str  # "healthy" or "unhealthy"
    message: str | None = None


class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", or "unhealthy"
    dependencies: dict[str, DependencyHealth]
    timestamp: datetime


async def _check_database(session: AsyncSession) -> DependencyHealth:
    try:
        await session.execute(text("SELECT 1"))
        return DependencyHealth(status="healthy")
    except Exception as exc:
        return DependencyHealth(status="unhealthy", message=str(exc))


async def _check_prefect() -> DependencyHealth:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.PREFECT_API_URL}/health")
            if resp.status_code == 200:
                return DependencyHealth(status="healthy")
            return DependencyHealth(
                status="unhealthy", message=f"HTTP {resp.status_code}"
            )
    except Exception as exc:
        return DependencyHealth(status="unhealthy", message=str(exc))


async def _check_otel() -> DependencyHealth:
    """Best-effort check: verify OTel endpoint is reachable."""
    settings = get_settings()
    try:
        # Simple TCP connect check to the gRPC endpoint
        async with httpx.AsyncClient(timeout=3.0) as client:
            # OTel collector typically runs gRPC; a simple GET won't work but
            # a connection attempt tells us the port is open
            await client.get(settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            return DependencyHealth(status="healthy")
    except Exception:
        # OTel is non-critical, so we just report unhealthy
        return DependencyHealth(
            status="unhealthy", message="OTel endpoint unreachable"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    db = await _check_database(session)
    prefect = await _check_prefect()
    otel = await _check_otel()

    deps = {"database": db, "prefect": prefect, "otel": otel}

    # Determine overall status
    critical_healthy = db.status == "healthy" and prefect.status == "healthy"
    all_healthy = critical_healthy and otel.status == "healthy"

    if all_healthy:
        status = "healthy"
    elif critical_healthy:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        dependencies=deps,
        timestamp=datetime.now(UTC),
    )
