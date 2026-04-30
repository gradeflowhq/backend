from datetime import datetime
from functools import lru_cache

import yaml

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.schemas.status import SectionStatus
from gradeflow_backend.utils.datetime import ensure_utc, is_after


def _make_status(updated_at: datetime | None, *, is_stale: bool) -> SectionStatus:
    return SectionStatus(
        updated_at=ensure_utc(updated_at) if updated_at is not None else None,
        is_stale=is_stale,
    )


@lru_cache(maxsize=256)
def _rubric_has_no_rules(rubric_yaml: str) -> bool:
    try:
        parsed = yaml.safe_load(rubric_yaml)
        if isinstance(parsed, dict):
            return not parsed.get("rules")
    except Exception:
        pass
    return False


def question_set_status(a: Assessment) -> SectionStatus:
    if not a.question_set_yaml:
        return _make_status(a.question_set_updated_at, is_stale=False)
    return _make_status(
        a.question_set_updated_at,
        is_stale=is_after(a.source_updated_at, a.question_set_updated_at),
    )


def rubric_status(a: Assessment) -> SectionStatus:
    if not a.rubric_yaml or _rubric_has_no_rules(a.rubric_yaml):
        return _make_status(a.rubric_updated_at, is_stale=False)
    qset = question_set_status(a)
    return _make_status(
        a.rubric_updated_at,
        is_stale=qset.is_stale or is_after(a.question_set_updated_at, a.rubric_updated_at),
    )


def results_status(a: Assessment) -> SectionStatus:
    rubric = rubric_status(a)
    return _make_status(
        a.results_updated_at,
        is_stale=rubric.is_stale or is_after(a.rubric_updated_at, a.results_updated_at),
    )
