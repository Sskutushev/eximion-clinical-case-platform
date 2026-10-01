"""Deterministic provider for tests, CI and offline evals.

Returns canned JSON keyed by the source text, so schema handling, validation,
error paths and metrics are all exercised with no credentials and no network.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from clinical_extraction.errors import ProviderError
from clinical_extraction.providers.base import ProviderResponse

FAKE_MODEL = "fake-extractor-1"


class FakeProvider:
    def __init__(
        self,
        responses: Mapping[str, str] | None = None,
        *,
        default: str | None = None,
        on_call: Callable[[int], None] | None = None,
        model: str = FAKE_MODEL,
    ) -> None:
        self._responses = dict(responses or {})
        self._default = default
        self._on_call = on_call
        self._model = model
        self.calls: list[str] = []

    @property
    def model(self) -> str:
        return self._model

    @classmethod
    def returning(cls, payload: dict[str, Any]) -> "FakeProvider":
        return cls(default=json.dumps(payload))

    def generate_structured(
        self, *, system_instruction: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> ProviderResponse:
        del system_instruction, json_schema
        self.calls.append(user_prompt)
        if self._on_call is not None:
            self._on_call(len(self.calls))

        for key, response in self._responses.items():
            if key in user_prompt:
                return ProviderResponse(text=response, model=self._model)
        if self._default is not None:
            return ProviderResponse(text=self._default, model=self._model)
        raise ProviderError("FakeProvider has no canned response for this prompt")
