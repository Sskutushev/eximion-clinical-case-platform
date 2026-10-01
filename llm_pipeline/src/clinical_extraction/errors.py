"""Typed, observable failures. Nothing in this pipeline fails silently."""


class ExtractionError(Exception):
    """Base class for every extraction failure."""


class ProviderError(ExtractionError):
    """The model provider failed (transport, quota, safety block, empty response)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class SchemaValidationError(ExtractionError):
    """The model returned JSON that breaks the contract.

    Not retried, not patched with a fallback: a bad clinical extraction has to
    surface rather than be guessed at.
    """

    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response
