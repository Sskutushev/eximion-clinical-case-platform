import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get("/health", summary="Liveness: process is up (no dependencies checked)")
def liveness() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get(
    "/health/ready",
    summary="Readiness: database reachable",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthStatus}},
)
def readiness(session: SessionDep, response: Response) -> HealthStatus:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("readiness check failed: database unreachable", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unavailable")
    return HealthStatus(status="ok")
