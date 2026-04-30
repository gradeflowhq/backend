import logging
from typing import cast

from fastapi import Depends, HTTPException, Request, status
from valkey import Valkey

from gradeflow_backend.config import get_settings
from gradeflow_backend.db import get_valkey

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_S = 60

_INCR_WITH_EXPIRE_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return current
"""


def _request_subject(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    client = request.client
    if client and client.host:
        return client.host
    return "unknown"


def _apply_rate_limit(*, request: Request, valkey_client: Valkey, scope: str, limit: int) -> None:
    key = f"rate-limit:grading:{scope}:{_request_subject(request)}"
    try:
        current = cast(
            int,
            valkey_client.eval(_INCR_WITH_EXPIRE_SCRIPT, 1, key, str(RATE_LIMIT_WINDOW_S)),
        )
        if current <= limit:
            return

        ttl = cast(int, valkey_client.ttl(key))
        retry_after = ttl if ttl > 0 else RATE_LIMIT_WINDOW_S
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to enforce grading rate limit", extra={"scope": scope})


def enforce_grading_run_rate_limit(
    request: Request,
    valkey_client: Valkey = Depends(get_valkey),
) -> None:
    _apply_rate_limit(
        request=request,
        valkey_client=valkey_client,
        scope="run",
        limit=get_settings().grading.run_requests_per_minute,
    )


def enforce_grading_preview_rate_limit(
    request: Request,
    valkey_client: Valkey = Depends(get_valkey),
) -> None:
    _apply_rate_limit(
        request=request,
        valkey_client=valkey_client,
        scope="preview",
        limit=get_settings().grading.preview_requests_per_minute,
    )
