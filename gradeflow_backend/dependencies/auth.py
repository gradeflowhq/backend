import logging
from functools import lru_cache
from typing import Any, cast

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from sqlalchemy.orm import Session

from gradeflow_backend.config import ZitadelSettings, get_settings
from gradeflow_backend.db import get_session
from gradeflow_backend.models.user import User
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.auth import ZitadelTokenPayload

logger = logging.getLogger(__name__)


AUTH_PROVIDER = "zitadel"


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """
    JWKS client — instantiated once, JWK set cached with a configurable TTL.

    Zitadel rotates signing keys without prior notice, so the cache is
    refreshed periodically (default 300 s) and on-demand when an unknown
    ``kid`` is encountered.

    A custom User-Agent header is required because some Zitadel hosts
    (or CDN/reverse-proxy layers) reject the default ``Python-urllib``
    user-agent with HTTP 403.
    """
    cfg = get_settings().zitadel
    return jwt.PyJWKClient(
        f"{cfg.authority}/oauth/v2/keys",
        cache_jwk_set=True,
        lifespan=cfg.jwks_cache_ttl,
        headers={"User-Agent": "GradeFlow-Backend/1.0"},
    )


@lru_cache(maxsize=1)
def _oauth2_scheme() -> OAuth2AuthorizationCodeBearer:
    """
    OAuth2 scheme — instantiated once at startup.
    Appends org_domain to the authorization URL when configured,
    scoping the Zitadel login to a single org so users type
    just their username without the @domain suffix.
    """
    cfg: ZitadelSettings = get_settings().zitadel
    auth_url = f"{cfg.authority}/oauth/v2/authorize"
    if cfg.org_domain:
        auth_url = f"{auth_url}?org_domain={cfg.org_domain}"
    return OAuth2AuthorizationCodeBearer(
        authorizationUrl=auth_url,
        tokenUrl=f"{cfg.authority}/oauth/v2/token",
        scopes={
            "openid": "OpenID Connect",
            "profile": "Profile",
            "email": "Email",
        },
    )


def _decode_token(token: str) -> ZitadelTokenPayload:
    """
    Validate and decode a Zitadel JWT.

    Uses RS256 + JWKS for local token validation (no network call per
    request apart from periodic JWKS refresh).  Validates audience and
    issuer per OIDC spec.

    When ``ZITADEL__AUDIENCE`` is configured it is used for audience
    validation; otherwise ``client_id`` is used as the default.

    Raises HTTP 401 on any validation failure.
    """
    cfg: ZitadelSettings = get_settings().zitadel
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        raw = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=cfg.audience or cfg.client_id,
            issuer=cfg.authority,
        )
        return ZitadelTokenPayload.model_validate(raw)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from e
    except jwt.InvalidAudienceError as e:
        logger.warning("Token audience mismatch: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience mismatch",
        ) from e
    except jwt.InvalidIssuerError as e:
        logger.warning("Token issuer mismatch: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer mismatch",
        ) from e
    except jwt.PyJWKClientError as e:
        logger.error("JWKS key resolution failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify token signature",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e


def _fetch_userinfo(access_token: str) -> dict[str, Any]:
    """
    Fetch user claims from the Zitadel userinfo endpoint.

    Zitadel JWT access tokens often omit profile claims (email, name)
    that are only available via the userinfo endpoint or ID-token.
    This function fills in those gaps so the backend can sync them
    to the local user table.
    """
    cfg = get_settings().zitadel
    url = f"{cfg.authority}/oidc/v1/userinfo"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())
    except httpx.HTTPError as exc:
        logger.warning("Userinfo request failed: %s", exc)
        return {}


def get_current_user(
    token: str = Depends(_oauth2_scheme()),
) -> tuple[ZitadelTokenPayload, str]:
    """FastAPI dependency — resolves the authenticated user from the bearer token.

    Returns both the decoded payload and the raw token string so that
    downstream dependencies can call the userinfo endpoint if needed.
    """
    return _decode_token(token), token


def get_current_db_user(
    current: tuple[ZitadelTokenPayload, str] = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> User:
    """
    FastAPI dependency — syncs the identity-provider user to the local DB
    and returns the ORM User instance.

    For existing users (looked up by provider identity) no network call
    is needed.  Only new or migrated users trigger a userinfo fetch when
    the email claim is absent from the access-token JWT.
    """
    token_payload, raw_token = current
    repo = UserRepository(db)

    # Fast path: user already linked by provider identity (no network I/O).
    user = repo.find_by_identity(AUTH_PROVIDER, token_payload.sub)
    if user:
        repo.sync_profile(user, email=token_payload.email, name=token_payload.name)
        return user

    # New or migrated user — email is required to create / link.
    email = token_payload.email
    name = token_payload.name
    if not email:
        userinfo = _fetch_userinfo(raw_token)
        email = userinfo.get("email")
        name = name or userinfo.get("name")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the email claim — ensure the 'email' scope is requested",
        )
    return repo.upsert_from_token(
        provider=AUTH_PROVIDER,
        provider_user_id=token_payload.sub,
        email=email,
        name=name,
    )


def get_current_user_id(
    user: User = Depends(get_current_db_user),
) -> str:
    """FastAPI dependency — resolves just the user ID. Ensures user is synced to DB."""
    return user.id
