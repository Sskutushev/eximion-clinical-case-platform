from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractionSettings(BaseSettings):
    """Provider configuration. Credentials come from ADC or the environment, never from git."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Vertex AI path (preferred in GCP): Application Default Credentials, no API key.
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    # Fallback for local experiments without a GCP project.
    gemini_api_key: SecretStr | None = None

    gemini_model: str = "gemini-2.5-flash"
    # Deterministic extraction: temperature 0, no sampling.
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, ge=256, le=32_768)
    request_timeout_seconds: int = Field(default=60, ge=5, le=600)
    max_attempts: int = Field(default=3, ge=1, le=10)

    @property
    def use_vertex(self) -> bool:
        return bool(self.google_cloud_project)

    @model_validator(mode="after")
    def _require_credentials(self) -> Self:
        if not self.google_cloud_project and not self.gemini_api_key:
            raise ValueError("Set GOOGLE_CLOUD_PROJECT (Vertex AI) or GEMINI_API_KEY (Gemini API)")
        return self


@lru_cache
def get_extraction_settings() -> ExtractionSettings:
    return ExtractionSettings()
