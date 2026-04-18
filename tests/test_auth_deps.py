"""Tests for the Zitadel authentication dependency layer.

These tests verify the actual token validation, userinfo fallback, and
user-sync logic that was previously untested because integration tests
override ``get_current_user`` entirely.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from gradeflow_backend.config import get_settings
from gradeflow_backend.dependencies.auth import (
    _decode_token,
    _fetch_userinfo,
    _jwks_client,
)
from gradeflow_backend.schemas.auth import ZitadelTokenPayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_AUTHORITY = "https://zitadel.test"
_TEST_CLIENT_ID = "test-client-id"
_TEST_AUDIENCE = ""


@pytest.fixture(autouse=True)
def _configure_zitadel() -> Generator[None, None, None]:
    """Ensure Zitadel settings are set for each test."""
    cfg = get_settings().zitadel
    orig_authority = cfg.authority
    orig_client_id = cfg.client_id
    orig_audience = cfg.audience

    cfg.authority = _TEST_AUTHORITY
    cfg.client_id = _TEST_CLIENT_ID
    cfg.audience = _TEST_AUDIENCE

    # Clear the lru_cache so each test picks up fresh settings.
    _jwks_client.cache_clear()

    yield

    cfg.authority = orig_authority
    cfg.client_id = orig_client_id
    cfg.audience = orig_audience
    _jwks_client.cache_clear()


def _make_raw_claims(**overrides: object) -> dict[str, object]:
    """Build a minimal valid Zitadel JWT claims dict."""
    claims: dict[str, object] = {
        "sub": "zitadel-user-123",
        "iss": _TEST_AUTHORITY,
        "aud": _TEST_CLIENT_ID,
        "email": "user@example.com",
        "name": "Test User",
    }
    claims.update(overrides)
    return claims


# ---------------------------------------------------------------------------
# _decode_token
# ---------------------------------------------------------------------------


class TestDecodeToken:
    """Unit tests for ``_decode_token``."""

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_valid_token_returns_payload(self, mock_jwks_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        claims = _make_raw_claims()

        with patch("gradeflow_backend.dependencies.auth.jwt.decode", return_value=claims):
            result = _decode_token("fake-token")

        assert isinstance(result, ZitadelTokenPayload)
        assert result.sub == "zitadel-user-123"
        assert result.email == "user@example.com"
        assert result.name == "Test User"

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_expired_token_raises_401(self, mock_jwks_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        with patch(
            "gradeflow_backend.dependencies.auth.jwt.decode",
            side_effect=pyjwt.ExpiredSignatureError("expired"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token("expired-token")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_audience_mismatch_raises_401(self, mock_jwks_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        with patch(
            "gradeflow_backend.dependencies.auth.jwt.decode",
            side_effect=pyjwt.InvalidAudienceError("bad aud"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token("bad-aud-token")

        assert exc_info.value.status_code == 401
        assert "audience" in exc_info.value.detail.lower()

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_issuer_mismatch_raises_401(self, mock_jwks_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        with patch(
            "gradeflow_backend.dependencies.auth.jwt.decode",
            side_effect=pyjwt.InvalidIssuerError("bad iss"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token("bad-iss-token")

        assert exc_info.value.status_code == 401
        assert "issuer" in exc_info.value.detail.lower()

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_jwks_failure_raises_401_with_signature_detail(
        self, mock_jwks_factory: MagicMock
    ) -> None:
        """Regression: JWKS fetch returning 403 should produce a clear error."""
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_client.get_signing_key_from_jwt.side_effect = pyjwt.PyJWKClientError(
            "HTTP Error 403: Forbidden"
        )

        with pytest.raises(HTTPException) as exc_info:
            _decode_token("any-token")

        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_invalid_token_raises_401(self, mock_jwks_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        with patch(
            "gradeflow_backend.dependencies.auth.jwt.decode",
            side_effect=pyjwt.InvalidTokenError("malformed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token("garbage")

        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    @patch("gradeflow_backend.dependencies.auth.get_settings")
    def test_audience_uses_config_audience_when_set(
        self, mock_get_settings: MagicMock, mock_jwks_factory: MagicMock
    ) -> None:
        """When ZITADEL__AUDIENCE is explicitly configured, it overrides client_id."""
        # Configure mock settings with explicit audience
        mock_zitadel = MagicMock()
        mock_zitadel.authority = _TEST_AUTHORITY
        mock_zitadel.client_id = _TEST_CLIENT_ID
        mock_zitadel.audience = "my-project-id"
        mock_settings = MagicMock()
        mock_settings.zitadel = mock_zitadel
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        claims = _make_raw_claims(aud="my-project-id")

        with patch(
            "gradeflow_backend.dependencies.auth.jwt.decode", return_value=claims
        ) as mock_decode:
            _decode_token("token")

        # Verify jwt.decode was called with the custom audience, not client_id
        _, call_kwargs = mock_decode.call_args
        assert call_kwargs["audience"] == "my-project-id"

    @patch("gradeflow_backend.dependencies.auth._jwks_client")
    def test_token_without_email_still_decodes(self, mock_jwks_factory: MagicMock) -> None:
        """Access tokens may omit email — _decode_token should not reject them."""
        mock_client = MagicMock()
        mock_jwks_factory.return_value = mock_client
        mock_key = MagicMock()
        mock_key.key = "fake-key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        claims = _make_raw_claims(email=None, name=None)

        with patch("gradeflow_backend.dependencies.auth.jwt.decode", return_value=claims):
            result = _decode_token("token-no-email")

        assert result.sub == "zitadel-user-123"
        assert result.email is None


# ---------------------------------------------------------------------------
# _fetch_userinfo
# ---------------------------------------------------------------------------


class TestFetchUserinfo:
    """Unit tests for the userinfo fallback."""

    @patch("gradeflow_backend.dependencies.auth.httpx.get")
    def test_returns_userinfo_on_success(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"email": "u@example.com", "name": "U"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = _fetch_userinfo("valid-token")

        assert result["email"] == "u@example.com"
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "Bearer valid-token" in call_kwargs[1]["headers"]["Authorization"]

    @patch("gradeflow_backend.dependencies.auth.httpx.get")
    def test_returns_empty_dict_on_http_error(self, mock_get: MagicMock) -> None:
        """Userinfo failure should not crash — returns empty dict for graceful fallback."""
        import httpx

        mock_get.side_effect = httpx.HTTPError("connection refused")

        result = _fetch_userinfo("bad-token")

        assert result == {}


# ---------------------------------------------------------------------------
# JWKS client configuration
# ---------------------------------------------------------------------------


class TestJwksClient:
    """Verify JWKS client setup (User-Agent header, caching)."""

    def test_jwks_client_has_custom_user_agent(self) -> None:
        """Regression: default Python urllib User-Agent is blocked by some hosts."""
        client = _jwks_client()
        # PyJWKClient stores headers as an instance attribute
        assert hasattr(client, "headers")
        assert "User-Agent" in client.headers
        assert "Python-urllib" not in client.headers["User-Agent"]

    def test_jwks_client_is_cached(self) -> None:
        """The JWKS client should be a singleton (lru_cache)."""
        a = _jwks_client()
        b = _jwks_client()
        assert a is b
