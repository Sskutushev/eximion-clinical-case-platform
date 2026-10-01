"""Migrations, configuration safety, health checks and error hygiene."""

import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, inspect

from app.core.config import Settings
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL, alembic_config, recreate_database

MIGRATION_DB_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/eximion_migration_test"


def test_migrations_upgrade_downgrade_roundtrip_and_match_models() -> None:
    recreate_database(MIGRATION_DB_URL)
    config = alembic_config(MIGRATION_DB_URL)

    command.upgrade(config, "head")
    command.check(config)  # raises if ORM models drifted from migrations
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(MIGRATION_DB_URL)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"clinical_cases", "case_findings", "case_answers", "case_submissions"} <= tables


def test_production_requires_admin_key() -> None:
    with pytest.raises(ValidationError, match="ADMIN_API_KEY"):
        Settings(
            environment="production",
            admin_api_key=None,
            database_url=SecretStr("postgresql+psycopg://u:p@127.0.0.1:1/none"),
        )


def test_production_hides_interactive_docs() -> None:
    app = create_app(
        Settings(
            environment="production",
            admin_api_key=SecretStr("k"),
            database_url=SecretStr("postgresql+psycopg://u:p@127.0.0.1:1/none"),
        )
    )
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_health_endpoints(client: TestClient) -> None:
    live = client.get("/health")
    assert live.json() == {"status": "ok"}
    assert live.headers["x-content-type-options"] == "nosniff"
    assert len(live.headers["x-request-id"]) == 32
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["x-request-id"] == "trace-123"


def test_readiness_reports_unavailable_database() -> None:
    settings = Settings(
        environment="test",
        database_url=SecretStr("postgresql+psycopg://nobody:x@127.0.0.1:1/none"),
        db_pool_timeout_seconds=1,
        db_connect_timeout_seconds=1,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_unhandled_errors_do_not_leak_internals() -> None:
    settings = Settings(
        environment="test",
        database_url=SecretStr("postgresql+psycopg://nobody:secret@127.0.0.1:1/none"),
        db_pool_timeout_seconds=1,
        db_connect_timeout_seconds=1,
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/api/v1/cases")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text
