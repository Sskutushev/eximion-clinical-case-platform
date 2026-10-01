"""Integration fixtures: a real PostgreSQL database migrated with Alembic (no create_all)."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://eximion:eximion@127.0.0.1:5433/eximion_test"
)
ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-API-Key": ADMIN_KEY}


def recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def migrated_db() -> str:
    recreate_database(TEST_DATABASE_URL)
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine(migrated_db: str) -> Iterator[Engine]:
    eng = create_engine(migrated_db)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Direct DB access for assertions; tables are truncated after every test."""
    with sessionmaker(bind=engine)() as session:
        yield session
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE case_submissions, case_answers, case_findings, clinical_cases "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def settings(migrated_db: str) -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr(migrated_db),
        admin_api_key=SecretStr(ADMIN_KEY),
        db_pool_size=2,
    )


@pytest.fixture
def client(settings: Settings, db: Session) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def case_payload() -> dict[str, Any]:
    return {
        "title": "Acute right lower quadrant pain",
        "patient_age": 24,
        "patient_sex": "male",
        "presentation": "Migratory abdominal pain for 18 hours with nausea.",
        "findings": [
            {"category": "symptom", "value": "Pain migrating to the right lower quadrant"},
            {"category": "laboratory", "value": "WBC 14.2 x10^9/L"},
        ],
        "answers": [
            {"text": "Acute appendicitis", "is_correct": True, "score_weight": 10},
            {"text": "Appendicitis", "is_correct": True, "score_weight": 10},
            {"text": "Mesenteric lymphadenitis", "is_correct": False, "score_weight": 3},
        ],
    }


@pytest.fixture
def created_case_id(client: TestClient, case_payload: dict[str, Any]) -> str:
    response = client.post("/api/v1/cases", json=case_payload, headers=ADMIN_HEADERS)
    assert response.status_code == 201, response.text
    case_id: str = response.json()["id"]
    return case_id
