from datetime import UTC, datetime, timedelta, timezone

from gradeflow_backend.utils.datetime import ensure_utc, is_after, utcnow


def test_utcnow_returns_aware_utc() -> None:
    now = utcnow()
    assert now.tzinfo is not None
    assert now.tzinfo == UTC


def test_ensure_utc_attaches_to_naive() -> None:
    naive = datetime(2024, 1, 15, 12, 0, 0)
    result = ensure_utc(naive)
    assert result.tzinfo == UTC
    assert result.year == 2024


def test_ensure_utc_converts_non_utc() -> None:
    eastern = timezone(timedelta(hours=-5))
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=eastern)
    result = ensure_utc(aware)
    assert result.tzinfo == UTC
    assert result.hour == 17  # 12 EST = 17 UTC


def test_ensure_utc_keeps_utc_unchanged() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
    result = ensure_utc(aware)
    assert result == aware


def test_is_after_both_none() -> None:
    assert is_after(None, None) is False


def test_is_after_later_none() -> None:
    assert is_after(None, datetime(2024, 1, 1, tzinfo=UTC)) is False


def test_is_after_reference_none() -> None:
    assert is_after(datetime(2024, 1, 1, tzinfo=UTC), None) is False


def test_is_after_later_is_later() -> None:
    earlier = datetime(2024, 1, 1, tzinfo=UTC)
    later = datetime(2024, 6, 1, tzinfo=UTC)
    assert is_after(later, earlier) is True


def test_is_after_later_is_earlier() -> None:
    earlier = datetime(2024, 1, 1, tzinfo=UTC)
    later = datetime(2024, 6, 1, tzinfo=UTC)
    assert is_after(earlier, later) is False


def test_is_after_equal() -> None:
    t = datetime(2024, 1, 1, tzinfo=UTC)
    assert is_after(t, t) is False
