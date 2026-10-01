import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import Settings

_admin_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def require_admin(
    settings: Annotated[Settings, Depends(get_app_settings)],
    api_key: Annotated[str | None, Security(_admin_key_header)],
) -> None:
    """Guards authoring endpoints. Open only when no key is configured (local dev)."""
    expected = settings.admin_api_key
    if expected is None:
        return
    if api_key is None or not hmac.compare_digest(
        api_key.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing admin API key")


SessionDep = Annotated[Session, Depends(get_session)]
