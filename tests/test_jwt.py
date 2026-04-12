from gradeflow_backend.security.jwt import (
    JwtError,
    assert_token_type,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trip() -> None:
    token = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["typ"] == "access"


def test_refresh_token_round_trip() -> None:
    token = create_refresh_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["typ"] == "refresh"


def test_access_token_has_standard_claims() -> None:
    token = create_access_token("u1")
    payload = decode_token(token)
    assert "iss" in payload
    assert "aud" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload


def test_custom_claims_merged() -> None:
    token = create_access_token("u1", claims={"role": "admin"})
    payload = decode_token(token)
    assert payload["role"] == "admin"


def test_assert_token_type_passes() -> None:
    assert_token_type({"typ": "access"}, "access")  # should not raise


def test_assert_token_type_mismatch() -> None:
    import pytest

    with pytest.raises(JwtError, match="expected access"):
        assert_token_type({"typ": "refresh"}, "access")


def test_decode_tampered_token_raises() -> None:
    import pytest

    token = create_access_token("u1")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(JwtError):
        decode_token(tampered)
