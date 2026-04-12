from gradeflow_backend.utils.engine import ENGINE_FIELDS, JSONValue, remove_engine_fields


def test_removes_top_level_engine_fields() -> None:
    data: JSONValue = {"name": "Rule1", "question_types": ["TEXT"], "constraints": {}, "points": 10}
    result = remove_engine_fields(data)
    assert result == {"name": "Rule1", "points": 10}


def test_removes_nested_engine_fields() -> None:
    data: JSONValue = {
        "rules": [
            {"name": "r1", "question_types": ["NUMERIC"], "value": 5},
            {"name": "r2", "constraints": {"min": 0}},
        ]
    }
    result = remove_engine_fields(data)
    assert result == {"rules": [{"name": "r1", "value": 5}, {"name": "r2"}]}


def test_preserves_non_engine_keys() -> None:
    data: JSONValue = {"key": "val", "nested": {"a": 1}}
    assert remove_engine_fields(data) == data


def test_scalars_passthrough() -> None:
    assert remove_engine_fields(42) == 42
    assert remove_engine_fields("str") == "str"
    assert remove_engine_fields(None) is None


def test_empty_structures() -> None:
    assert remove_engine_fields({}) == {}
    assert remove_engine_fields([]) == []


def test_engine_fields_constant_contains_expected() -> None:
    assert "question_types" in ENGINE_FIELDS
    assert "constraints" in ENGINE_FIELDS
