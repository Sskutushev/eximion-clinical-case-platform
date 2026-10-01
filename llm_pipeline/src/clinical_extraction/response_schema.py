"""The JSON schema sent to the model, as opposed to the one we validate against.

Gemini's constrained decoding rejects a schema whose state space is too large:

    The specified schema produces a constraint that has too many states for
    serving. Typical causes are ... integers or numbers with minimum/maximum
    bounds or strings with complex formats.

Our Pydantic contract carries exactly those: length limits on every string,
ranges on age and score weight, item counts on the arrays. So the model is given
the shape — objects, properties, types, enums, which fields are required — and
the bounds are left out.

Nothing is lost by this. The bounds are still enforced, by Pydantic, on the
response. The model guides generation; the validator decides what is acceptable.
"""

from typing import Any

# Keywords that constrain values rather than describe shape.
_UNSUPPORTED = frozenset(
    {
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "uniqueItems",
        "additionalProperties",
    }
)


def simplify(schema: Any) -> Any:
    """Strip value constraints, keep structure, enums and required fields."""
    if isinstance(schema, list):
        return [simplify(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    return {key: simplify(value) for key, value in schema.items() if key not in _UNSUPPORTED}
