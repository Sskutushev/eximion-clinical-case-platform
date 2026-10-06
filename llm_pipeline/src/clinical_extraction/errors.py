"""Typed, observable failures. Nothing in this pipeline fails silently."""


class ExtractionError(Exception):
    """Base class for every extraction failure."""


class ProviderError(ExtractionError):
    """The model provider failed (transport, quota, safety block, empty response)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ContentBlockedError(ProviderError):
    """The model returned nothing because content filtering stopped it.

    A different thing from a quota or transport failure: the request reached the
    model and the model declined. Retrying will not help, and the eval reports
    it separately so a blocked case is not mistaken for an outage.
    """

    def __init__(self, message: str, *, feedback: str | None = None) -> None:
        super().__init__(message, retryable=False)
        self.feedback = feedback


class SchemaValidationError(ExtractionError):
    """The model returned JSON that breaks the contract.

    Not retried, not patched with a fallback: a bad clinical extraction has to
    surface rather than be guessed at.
    """

    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class DecisionError(Exception):
    """Base class for failures in the decision layer (verification of an extraction).

    Kept apart from `ExtractionError` on purpose: a verifier that is down does
    not make the extraction wrong, it makes it unverified.
    """


class DecisionProviderError(DecisionError):
    """A decision provider failed (transport, quota, auth, malformed answer)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class UnsupportedDecisionTaskError(DecisionError):
    """The provider has no model for this task, so it cannot answer it."""
