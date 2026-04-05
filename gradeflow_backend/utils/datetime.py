from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """
    Return a timezone-aware UTC datetime.

    - If ``dt`` is already timezone-aware, convert it to UTC.
    - If ``dt`` is naive, assume it is UTC and attach the UTC tzinfo.

    Args:
        dt: The datetime to normalise.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def is_after(later: datetime | None, reference: datetime | None) -> bool:
    """
    Return True if ``later`` is strictly after ``reference``.

    Returns False if either argument is None, avoiding the need for
    None-guards at every call site.

    Args:
        later: The candidate datetime (may be None).
        reference: The reference datetime (may be None).

    Returns:
        True if both are non-None and ``later`` > ``reference``.
    """
    if later is None or reference is None:
        return False
    return ensure_utc(later) > ensure_utc(reference)
