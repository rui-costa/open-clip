"""Minimal JSON Schema validator.

Covers the subset of draft-07 the prompt schemas in backend/config/schemas
actually use: `type`, `properties`, `required`, `items`, `enum`,
`additionalProperties` (boolean form), and arbitrary nesting of those. Anything
else in a schema document is ignored rather than rejected, so an unsupported
keyword never blocks a task that is otherwise well formed.

Kept in-tree instead of pulling in `jsonschema` so validation adds no runtime
dependency to the pipeline.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    # bool is a subclass of int in Python, so it has to be excluded explicitly
    # or `true` would satisfy an integer/number field.
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_name(value: Any) -> str:
    for name, check in _TYPE_CHECKS.items():
        if name != "number" and check(value):
            return name
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def validate(instance: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Returns a list of human-readable validation errors. Empty means valid."""
    errors: List[str] = []

    if not isinstance(schema, dict):
        return errors

    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        checks = [_TYPE_CHECKS[t] for t in allowed if t in _TYPE_CHECKS]
        if checks and not any(check(instance) for check in checks):
            errors.append(
                f"{path}: expected type {'/'.join(allowed)}, got {_type_name(instance)}"
            )
            # A wrong type makes every nested rule meaningless, so stop here.
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum {schema['enum']}")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property '{key}'")

        for key, subschema in properties.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))

        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))

    return errors
