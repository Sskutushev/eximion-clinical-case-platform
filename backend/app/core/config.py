from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# Matches docker-compose, so running from source needs no .env.
LOCAL_DATABASE_URL = "postgresql+psycopg://eximion:eximion@127.0.0.1:5433/eximion"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (12-factor)."""

    # Repo-root .env when run from backend/, or a local one; real env vars always win.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "test", "production"] = "local"

    # Either a full DATABASE_URL, or the parts below.
    #
    # Cloud Run does not expand variable references inside environment values,
    # so a URL containing ${DB_PASSWORD} would arrive with that text as the
    # password. In Cloud Run the password comes from Secret Manager as its own
    # variable and the URL is assembled here, at runtime.
    database_url: SecretStr | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_name: str | None = None
    db_host: str | None = None
    db_port: int = Field(default=5432, ge=1, le=65535)
    # Cloud SQL connects over a Unix socket: /cloudsql/PROJECT:REGION:INSTANCE
    instance_unix_socket: str | None = None
    # Cloud Run multiplies connections by instance count: keep per-instance pool small.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=2, ge=0, le=50)
    db_pool_timeout_seconds: int = Field(default=10, ge=1, le=120)
    # Fail fast when the database is unreachable instead of hanging a request slot.
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)
    admin_api_key: SecretStr | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _fail_closed_in_production(self) -> Self:
        if self.environment == "production" and not self.admin_api_key:
            raise ValueError("ADMIN_API_KEY must be set when ENVIRONMENT=production")
        configured = self.database_url is not None or bool(
            self.db_user and self.db_password and self.db_name
        )
        if not configured and self.environment != "local":
            raise ValueError(
                "Set DATABASE_URL, or DB_USER, DB_PASSWORD and DB_NAME "
                "with either DB_HOST or INSTANCE_UNIX_SOCKET"
            )
        return self

    @property
    def sqlalchemy_url(self) -> str:
        """The connection URL, from DATABASE_URL or assembled from the parts."""
        if self.database_url is not None:
            return self.database_url.get_secret_value()

        if not (self.db_user and self.db_password and self.db_name):
            # Only reachable in local development; the validator rejects the
            # rest at startup.
            return LOCAL_DATABASE_URL

        url = URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            database=self.db_name,
            host=None if self.instance_unix_socket else self.db_host,
            port=None if self.instance_unix_socket else self.db_port,
            # psycopg takes the Cloud SQL socket directory as the `host` param.
            query={"host": self.instance_unix_socket} if self.instance_unix_socket else {},
        )
        return url.render_as_string(hide_password=False)

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
