from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Raw structured JSON text returned by a model, plus attribution metadata."""

    text: str
    model: str
    usage: dict[str, int] | None = None


@runtime_checkable
class ExtractionProvider(Protocol):
    """Seam between the pipeline and a model vendor.

    Keeping this a Protocol lets the extractor, the eval harness and the tests
    run against a fake provider with no network access and no credentials.
    """

    @property
    def model(self) -> str: ...

    def generate_structured(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> ProviderResponse: ...
