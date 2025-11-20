from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from typing import Any, TypeAlias, cast

import pytest
from fastapi.testclient import TestClient
from gradeflow_engine.rules.models.length import LengthRule

# Engine models with nullable primitives
from gradeflow_engine.rules.models.numeric_range import NumericRangeRule

from gradeflow_backend.main import app
from gradeflow_backend.openapi import convert_primitive_anyof_merge_equal_or_absent

# Backend schemas with nullable primitives and other shapes
from gradeflow_backend.schemas.assessments import AssessmentResponse
from gradeflow_backend.schemas.auth import MeResponse, SignupRequest
from gradeflow_backend.schemas.grading import GradingExportRequest
from gradeflow_backend.schemas.rubrics import RubricResponse
from gradeflow_backend.schemas.submissions import SubmissionsResponse

# -----------------------
# JSON typing helpers (3.11)
# -----------------------
JSONScalar = str | int | float | bool | None
JSONDict = dict[str, "JSONValue"]
JSONList = list["JSONValue"]
JSONValue = JSONScalar | JSONDict | JSONList

# -----------------------
# OpenAPI type aliases
# -----------------------
OpenAPI: TypeAlias = dict[str, Any]
SchemaDict: TypeAlias = dict[str, Any]
SchemasDict: TypeAlias = dict[str, SchemaDict]


# -----------------------
# Pytest fixture
# -----------------------
@pytest.fixture(autouse=True)
def reset_openapi_cache() -> Generator[None, None, None]:
    app.openapi_schema = None
    yield
    app.openapi_schema = None


# -----------------------
# Typed helpers
# -----------------------
def _client_openapi() -> OpenAPI:
    client = TestClient(app)
    data = client.get("/openapi.json").json()
    assert isinstance(data, dict)
    return cast(OpenAPI, data)


def _components(openapi: OpenAPI) -> dict[str, Any]:
    comps: Any = openapi.get("components")
    assert isinstance(comps, dict), "OpenAPI components missing"
    return comps


def _schemas(openapi: OpenAPI) -> SchemasDict:
    comps: dict[str, Any] = _components(openapi)
    raw: dict[Any, Any] | None = comps.get("schemas")
    assert isinstance(raw, dict), "OpenAPI components.schemas missing"

    narrowed: SchemasDict = {}
    for key, val in raw.items():
        if not isinstance(key, str):
            continue
        if not isinstance(val, dict):
            continue
        val_dict: SchemaDict = cast(SchemaDict, val)
        narrowed[key] = val_dict
    return narrowed


def _get_schema(openapi: OpenAPI, model_cls: type) -> SchemaDict:
    name = model_cls.__name__
    sch = _schemas(openapi)
    assert name in sch, f"{name} not in components"
    return sch[name]


def _resolve_ref(openapi: OpenAPI, node: SchemaDict) -> SchemaDict:
    ref = node.get("$ref")
    if isinstance(ref, str):
        parts = ref.split("/")
        if len(parts) >= 4 and parts[1] == "components" and parts[2] == "schemas":
            name = parts[-1]
            target = _schemas(openapi).get(name)
            if isinstance(target, dict):
                return target
    return node


def _props(schema: SchemaDict) -> SchemaDict:
    props = schema.get("properties")
    assert isinstance(props, dict), "schema.properties missing"
    return cast(SchemaDict, props)


def _get_prop_schema(openapi: OpenAPI, schema: SchemaDict, prop_name: str) -> SchemaDict:
    props = _props(schema)
    prop = props.get(prop_name)
    assert isinstance(prop, dict), f"schema.properties[{prop_name!r}] missing"
    return _resolve_ref(openapi, cast(SchemaDict, prop))


def _find_schema_with_property(openapi: OpenAPI, prop_name: str) -> SchemaDict | None:
    for sch in _schemas(openapi).values():
        s = _resolve_ref(openapi, sch)
        props = s.get("properties")
        if isinstance(props, dict) and prop_name in props:
            return s
    return None


# Local traversal helper for unit tests (avoid importing private functions)
def _traverse_and_convert_local(node: JSONValue) -> None:
    if isinstance(node, dict):
        for value in list(node.values()):
            _traverse_and_convert_local(value)
        # node is dict[str, JSONValue] at this point
        convert_primitive_anyof_merge_equal_or_absent(node)
    elif isinstance(node, list):
        for item in node:
            _traverse_and_convert_local(item)
    else:
        return


# -----------------------
# Tests
# -----------------------
def test_openapi_union_primitive_type_array() -> None:
    openapi: OpenAPI = _client_openapi()
    model_schema: SchemaDict = _get_schema(openapi, SignupRequest)
    name_schema: SchemaDict = _get_prop_schema(openapi, model_schema, "name")

    assert "type" in name_schema, "Union schema didn't use primitive type array"
    tval = name_schema["type"]
    assert isinstance(tval, list)
    typed_tval: list[str] = cast(list[str], tval)
    assert set(typed_tval) == {"string", "null"}
    assert name_schema.get("maxLength") == 255


def test_openapi_idempotent() -> None:
    first: OpenAPI = _client_openapi()
    second: OpenAPI = _client_openapi()
    assert first == second, "OpenAPI output changed across repeated generation"


# -----------------------
# Unit tests (transformer)
# -----------------------
def test_transformer_simple_merge_with_absent_keys() -> None:
    schema: JSONDict = {"anyOf": [{"type": "string", "maxLength": 255}, {"type": "null"}]}
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema.get("anyOf") is None
    assert schema["type"] == ["string", "null"]
    assert schema["maxLength"] == 255


def test_transformer_conflicting_constraints_abort() -> None:
    orig: JSONDict = {
        "anyOf": [{"type": "string", "pattern": "^a+$"}, {"type": "string", "pattern": "^b+$"}]
    }
    schema = deepcopy(orig)
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema == orig


def test_transformer_non_primitive_branch_abort() -> None:
    orig: JSONDict = {
        "anyOf": [{"type": "string"}, {"type": "object", "properties": {"x": {"type": "number"}}}]
    }
    schema = deepcopy(orig)
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema == orig


def test_transformer_ref_branch_abort() -> None:
    orig: JSONDict = {"anyOf": [{"type": "string"}, {"$ref": "#/components/schemas/Something"}]}
    schema = deepcopy(orig)
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema == orig


def test_transformer_deduplicates_and_preserves_order() -> None:
    schema: JSONDict = {"anyOf": [{"type": "string"}, {"type": "null"}, {"type": "string"}]}
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema.get("anyOf") is None
    assert schema["type"] == ["string", "null"]


def test_transformer_nested_traversal() -> None:
    root: JSONDict = {
        "type": "object",
        "properties": {
            "field": {
                "anyOf": [{"type": "string", "maxLength": 10}, {"type": "null"}],
                "title": "Field",
            }
        },
    }
    _traverse_and_convert_local(root)

    props: SchemaDict = _props(root)
    field_schema = props["field"]
    assert isinstance(field_schema, dict)
    assert "anyOf" not in field_schema
    tval = field_schema["type"]
    assert isinstance(tval, list)
    typed_tval: list[str] = cast(list[str], tval)
    assert typed_tval == ["string", "null"]
    assert field_schema["maxLength"] == 10
    assert field_schema.get("title") == "Field"


def test_transformer_noop_when_no_anyof() -> None:
    orig: JSONDict = {"type": "string", "title": "Name"}
    schema = deepcopy(orig)
    convert_primitive_anyof_merge_equal_or_absent(schema)
    assert schema == orig


# -----------------------
# Real models (engine/backend)
# -----------------------
def test_nullable_string_fields_converted_in_backend_models() -> None:
    openapi: OpenAPI = _client_openapi()

    ar_schema: SchemaDict = _get_schema(openapi, AssessmentResponse)
    desc: SchemaDict = _get_prop_schema(openapi, ar_schema, "description")
    tval = desc.get("type")
    assert isinstance(tval, list)
    typed_tval: list[str] = cast(list[str], tval)
    assert set(typed_tval) == {"string", "null"}

    me_schema: SchemaDict = _get_schema(openapi, MeResponse)
    name: SchemaDict = _get_prop_schema(openapi, me_schema, "name")
    tval2 = name.get("type")
    assert isinstance(tval2, list)
    typed_tval2: list[str] = cast(list[str], tval2)
    assert set(typed_tval2) == {"string", "null"}


def test_nullable_number_integer_fields_converted_in_engine_rule_models() -> None:
    openapi: OpenAPI = _client_openapi()

    nrr_schema: SchemaDict = _get_schema(openapi, NumericRangeRule)
    min_value: SchemaDict = _get_prop_schema(openapi, nrr_schema, "min_value")
    max_value: SchemaDict = _get_prop_schema(openapi, nrr_schema, "max_value")
    tmin = min_value.get("type")
    tmax = max_value.get("type")
    assert isinstance(tmin, list) and isinstance(tmax, list)
    typed_tmin: list[str] = cast(list[str], tmin)
    typed_tmax: list[str] = cast(list[str], tmax)
    assert set(typed_tmin) == {"number", "null"}
    assert set(typed_tmax) == {"number", "null"}

    lr_schema: SchemaDict = _get_schema(openapi, LengthRule)
    min_length: SchemaDict = _get_prop_schema(openapi, lr_schema, "min_length")
    max_length: SchemaDict = _get_prop_schema(openapi, lr_schema, "max_length")
    tminl = min_length.get("type")
    tmaxl = max_length.get("type")
    assert isinstance(tminl, list) and isinstance(tmaxl, list)
    typed_tminl: list[str] = cast(list[str], tminl)
    typed_tmaxl: list[str] = cast(list[str], tmaxl)
    assert set(typed_tminl) == {"integer", "null"}
    assert set(typed_tmaxl) == {"integer", "null"}


def test_patcher_preserves_discriminated_unions_where_used() -> None:
    """
    Verify Question union (inside question_map additionalProperties) and QuestionRule union
    (inside Rubric.rules items) remain object unions with discriminators.
    """
    openapi: OpenAPI = _client_openapi()

    qs_like = _find_schema_with_property(openapi, "question_map")
    assert isinstance(qs_like, dict), "Could not find a schema with 'question_map' property"
    qmap_prop: SchemaDict = _get_prop_schema(openapi, qs_like, "question_map")
    value_schema = qmap_prop.get("additionalProperties")
    assert isinstance(value_schema, dict), "question_map.additionalProperties missing"
    value_schema = _resolve_ref(openapi, cast(SchemaDict, value_schema))

    union = value_schema.get("oneOf") or value_schema.get("anyOf")
    assert isinstance(union, list)
    union_list: list[SchemaDict] = cast(list[SchemaDict], union)
    assert len(union_list) > 0
    if "type" in value_schema:
        assert value_schema["type"] == "object"
    discriminator = value_schema.get("discriminator")
    assert isinstance(discriminator, dict) and "propertyName" in discriminator

    rub_like = _find_schema_with_property(openapi, "rules")
    assert isinstance(rub_like, dict), "Could not find a schema with 'rules' property"
    rules_prop: SchemaDict = _get_prop_schema(openapi, rub_like, "rules")
    items_schema = rules_prop.get("items")
    assert isinstance(items_schema, dict), "rubric.rules.items missing"
    items_schema = _resolve_ref(openapi, cast(SchemaDict, items_schema))

    union2 = items_schema.get("oneOf") or items_schema.get("anyOf")
    assert isinstance(union2, list)
    union2_list: list[SchemaDict] = cast(list[SchemaDict], union2)
    assert len(union2_list) > 0
    if "type" in items_schema:
        assert items_schema["type"] == "object"
    discriminator2 = items_schema.get("discriminator")
    assert isinstance(discriminator2, dict) and "propertyName" in discriminator2


def test_other_backend_response_shapes() -> None:
    """
    Exercise RubricResponse, SubmissionsResponse, and GradingExportRequest.
    Validate patcher doesn't alter non-primitive unions.
    """
    openapi: OpenAPI = _client_openapi()

    rr_schema: SchemaDict = _get_schema(openapi, RubricResponse)
    rubric_prop: SchemaDict = _get_prop_schema(openapi, rr_schema, "rubric")
    assert not isinstance(rubric_prop.get("type"), list), (
        "rubric should not be a primitive type array"
    )

    sr_schema: SchemaDict = _get_schema(openapi, SubmissionsResponse)
    raw_prop: SchemaDict = _get_prop_schema(openapi, sr_schema, "raw_submissions")
    assert raw_prop.get("type") == "array"

    ger_schema: SchemaDict = _get_schema(openapi, GradingExportRequest)
    kwargs_prop: SchemaDict = _get_prop_schema(openapi, ger_schema, "submissions_saver_kwargs")
    tkwargs = kwargs_prop.get("type")
    assert not isinstance(tkwargs, list), (
        "object-or-null union should not be converted to primitive type array"
    )
    anyof = kwargs_prop.get("anyOf")
    if isinstance(anyof, list):
        anyof_list: list[SchemaDict] = cast(list[SchemaDict], anyof)
        types: set[str] = set()
        for br in anyof_list:
            t = br.get("type")
            if isinstance(t, str):
                types.add(t)
        assert "object" in types and "null" in types
    else:
        # Some generators may emit nullable object without anyOf but with a direct object type
        assert kwargs_prop.get("type") == "object"
