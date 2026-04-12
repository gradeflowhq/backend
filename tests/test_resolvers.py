import pytest

from gradeflow_backend.services.exceptions import BadRequestError
from gradeflow_backend.utils.resolvers import resolve_or_require


def test_use_stored_calls_load() -> None:
    result = resolve_or_require(
        use_stored=True,
        load=lambda: "stored_value",
        override=None,
        field_name="rubric",
    )
    assert result == "stored_value"


def test_use_stored_ignores_override() -> None:
    result = resolve_or_require(
        use_stored=True,
        load=lambda: "stored",
        override="override",
        field_name="rubric",
    )
    assert result == "stored"


def test_not_stored_returns_override() -> None:
    result = resolve_or_require(
        use_stored=False,
        load=lambda: "should_not_call",
        override="my_override",
        field_name="rubric",
    )
    assert result == "my_override"


def test_not_stored_none_override_raises() -> None:
    with pytest.raises(BadRequestError, match="rubric"):
        resolve_or_require(
            use_stored=False,
            load=lambda: "x",
            override=None,
            field_name="rubric",
        )


def test_not_stored_does_not_call_load() -> None:
    called = False

    def spy_load() -> str:
        nonlocal called
        called = True
        return "x"

    resolve_or_require(
        use_stored=False,
        load=spy_load,
        override="value",
        field_name="f",
    )
    assert called is False
