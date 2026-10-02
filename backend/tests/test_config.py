"""Database configuration.

Cloud Run does not expand variable references inside environment values, so a
URL containing ${DB_PASSWORD} arrives with that text as the password. The URL is
therefore assembled here, from parts, at runtime.
"""

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import make_url

from app.core.config import LOCAL_DATABASE_URL, Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": None,
        "db_user": "eximion_app",
        "db_password": SecretStr("s3cret"),
        "db_name": "eximion",
        "db_host": "10.0.0.5",
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_explicit_url_is_used_as_is() -> None:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://u:p@host:5432/db"))

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"


def test_private_ip_host_and_port_are_used_as_given() -> None:
    """Cloud Run reaches Cloud SQL over its private IP, not an Auth Proxy socket."""
    settings = _settings(db_host="10.0.0.5", db_port=5433)

    url = make_url(settings.sqlalchemy_url)

    assert (url.host, url.port) == ("10.0.0.5", 5433)
    assert url.database == "eximion"
    assert url.username == "eximion_app"
    assert "host" not in url.query


def test_password_special_characters_survive_the_round_trip() -> None:
    """A generated password contains / @ : # — naive interpolation would corrupt it."""
    password = "p@ss/w:rd#1+2 3"
    settings = _settings(db_password=SecretStr(password))

    assert make_url(settings.sqlalchemy_url).password == password


@pytest.mark.parametrize(
    "missing", [{"db_user": None}, {"db_password": None}, {"db_name": None}, {"db_host": None}]
)
def test_incomplete_configuration_is_rejected_outside_local(missing: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        _settings(environment="production", admin_api_key=SecretStr("k"), **missing)


def test_local_falls_back_to_the_compose_database() -> None:
    """Running from source after `docker compose up postgres` needs no .env."""
    settings = Settings(environment="local", database_url=None)

    assert settings.sqlalchemy_url == LOCAL_DATABASE_URL


def test_a_url_with_an_unexpanded_variable_is_visible_as_such() -> None:
    """Guards the Cloud Run footgun: the value arrives literally, not expanded."""
    settings = Settings(database_url=SecretStr("postgresql+psycopg://u:${DB_PASSWORD}@10.0.0.5/db"))

    assert "${DB_PASSWORD}" in settings.sqlalchemy_url
