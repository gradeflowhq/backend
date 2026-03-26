import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from gradeflow_backend.config import get_settings


class JwtError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(sub: str, claims: dict[str, Any] | None = None) -> str:
    cfg = get_settings().security
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
        "sub": sub,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(minutes=cfg.jwt_access_expires_minutes)).timestamp()),
        "jti": jti,
        "typ": "access",
    }
    if claims:
        payload.update(claims)
    headers: dict[str, Any] = {}
    if cfg.jwt_kid:
        headers["kid"] = cfg.jwt_kid
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm, headers=headers)


def create_refresh_token(sub: str, claims: dict[str, Any] | None = None) -> str:
    cfg = get_settings().security
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
        "sub": sub,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(days=cfg.jwt_refresh_expires_days)).timestamp()),
        "jti": jti,
        "typ": "refresh",
    }
    if claims:
        payload.update(claims)
    headers: dict[str, Any] = {}
    if cfg.jwt_kid:
        headers["kid"] = cfg.jwt_kid
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm, headers=headers)


def decode_token(token: str) -> dict[str, Any]:
    cfg = get_settings().security
    try:
        payload = jwt.decode(
            token,
            cfg.jwt_secret,
            algorithms=[cfg.jwt_algorithm],
            audience=cfg.jwt_audience,
            issuer=cfg.jwt_issuer,
        )
        return payload  # PyJWT returns Any
    except jwt.PyJWTError as e:
        raise JwtError(str(e)) from e


def assert_token_type(payload: dict[str, Any], expected_typ: str) -> None:
    typ = payload.get("typ")
    if typ != expected_typ:
        raise JwtError(f"Invalid token type: expected {expected_typ}, got {typ}")
