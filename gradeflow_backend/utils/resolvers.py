from collections.abc import Callable
from typing import TypeVar

from gradeflow_backend.services.exceptions import BadRequestError

T = TypeVar("T")


def resolve_or_require(
    *,
    use_stored: bool,
    load: Callable[[], T],
    override: T | None,
    field_name: str,
) -> T:
    """
    Generic "use stored or require an explicit override" resolver.

    Used throughout the service layer wherever a caller can either rely on
    a persisted value (e.g. the stored rubric) or supply their own inline
    value for a one-off operation.

    Args:
        use_stored:  If True, call ``load()`` and return its result.
        load:        Zero-argument callable that loads the stored value.
                     Called only when ``use_stored`` is True.
                     May raise ``NotFoundError`` if nothing is stored yet.
        override:    Caller-supplied value used when ``use_stored`` is False.
        field_name:  Human-readable name of the field, used in the error
                     message when ``use_stored`` is False but ``override``
                     is None.

    Returns:
        The resolved value — either from storage or from the override.

    Raises:
        BadRequestError: When ``use_stored`` is False and ``override`` is None.
        NotFoundError:   Propagated from ``load()`` when nothing is stored.

    Example::

        rubric = resolve_or_require(
            use_stored=req.use_stored_rubric,
            load=lambda: self._load_rubric(a),
            override=req.rubric,
            field_name="rubric",
        )
    """
    if use_stored:
        return load()
    if override is None:
        raise BadRequestError(
            f"'{field_name}' must be provided when 'use_stored_{field_name}' is False."
        )
    return override
