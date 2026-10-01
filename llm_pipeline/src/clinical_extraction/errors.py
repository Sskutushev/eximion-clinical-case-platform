"""Typed, observable failures. Nothing in this pipeline fails silently."""


class ExtractionError(Exception):
    """Base class for every extraction failure."""


class ProviderError(ExtractionError):
    """The model provider failed (transport, quota, safety block, empty response)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class SchemaValidationError(ExtractionError):
    """The model returned JSON that does not satisfy the contract.

    Deliberately NOT retried and never repaired with a fallback: a malformed
    clinical extraction must surface, not be guessed at.
    """

    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response
