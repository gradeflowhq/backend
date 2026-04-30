from collections.abc import Iterator
from typing import Any, Literal

from fastapi import FastAPI

PrimitiveType = Literal["string", "integer", "number", "boolean", "null"]
SchemaDict = dict[str, Any]
PRIMITIVE_TYPES: set[PrimitiveType] = {"string", "integer", "number", "boolean", "null"}


def convert_primitive_anyof_merge_equal_or_absent(schema: SchemaDict) -> None:
    """
    Convert anyOf of primitive branches into `type: [..]` and lift simple constraints when safe.

    Rules:
      - All branches must be dicts with a primitive 'type' and no $ref.
      - Extra keys beyond 'type' are allowed, but for each key:
          - All branches that include the key must have the exact same value.
          - Branches may omit the key (treated as absent).
      - If any key conflicts (different values across branches), do not convert.

    Example:
      anyOf: [{type: "string", maxLength: 255}, {type: "null"}]
      -> type: ["string", "null"], maxLength: 255
    """
    anyof = schema.get("anyOf")
    if not isinstance(anyof, list) or not anyof:
        return

    branches: list[SchemaDict] = []
    for br in anyof:
        if not isinstance(br, dict):
            return
        if "$ref" in br:
            return
        t = br.get("type")
        if t not in PRIMITIVE_TYPES:
            return
        branches.append(br)

    # Collect types (preserve order, dedupe)
    seen_types: set[PrimitiveType] = set()
    type_array: list[PrimitiveType] = []
    for br in branches:
        t = br["type"]
        if t not in seen_types:
            seen_types.add(t)
            type_array.append(t)

    # Merge constraints: key must be equal across all branches that specify it
    merged: SchemaDict = {}
    candidate_keys: set[str] = set()
    for br in branches:
        candidate_keys.update(k for k in br.keys() if k != "type")

    for key in candidate_keys:
        first_value = None
        seen_any = False
        for br in branches:
            if key in br:
                v = br[key]
                if not seen_any:
                    first_value = v
                    seen_any = True
                else:
                    if v != first_value:
                        # Conflict -> abort conversion
                        return
        if seen_any:
            merged[key] = first_value

    # Apply conversion
    schema.pop("anyOf", None)
    schema["type"] = type_array
    for k, v in merged.items():
        schema[k] = v


def _iter_schema_dicts(node: object) -> Iterator[SchemaDict]:
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_schema_dicts(value)
        yield node
        return
    if isinstance(node, list):
        for item in node:
            yield from _iter_schema_dicts(item)


def patch_openapi_union_format(app: FastAPI) -> None:
    """
    Patch app.openapi to post-process component schemas.
    Operates in-place on FastAPI's cached OpenAPI dict.
    """
    original_openapi = app.openapi

    def patched_openapi() -> SchemaDict:
        spec = original_openapi()
        components = spec.get("components")
        if isinstance(components, dict):
            schemas = components.get("schemas")
            if isinstance(schemas, dict):
                for s in schemas.values():
                    for node in _iter_schema_dicts(s):
                        convert_primitive_anyof_merge_equal_or_absent(node)
        return spec

    app.openapi = patched_openapi  # type: ignore[method-assign]
