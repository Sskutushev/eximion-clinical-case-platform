"""Exception -> HTTP mapping. Clients never see stack traces, SQL or internal identifiers."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.services.cases import CaseNotFoundError

logger = logging.getLogger(__name__)


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def _case_not_found(_: Request, __: Exception) -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "Clinical case not found")


async def _integrity_error(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("integrity error", extra={"error_type": type(exc).__name__})
    return _error(status.HTTP_409_CONFLICT, "Request conflicts with existing data")


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error", exc_info=exc)
    return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CaseNotFoundError, _case_not_found)
    app.add_exception_handler(IntegrityError, _integrity_error)
    app.add_exception_handler(Exception, _unhandled)
