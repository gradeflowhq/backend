from gradeflow_backend.schemas.auth import TokenPairResponse
from tests.helpers.api import ApiClient


def test_signup_and_me(api: ApiClient) -> None:
    me = api.me()
    assert me.email == "user@example.com"
    assert me.name is None or isinstance(me.name, str)


def test_oauth2_token(api: ApiClient) -> None:
    tokens = api.token("user@example.com", "Super-Strong-Pass-123!")
    assert isinstance(tokens.access_token, str)
    assert isinstance(tokens.refresh_token, str)


def test_refresh_and_logout(api: ApiClient) -> None:
    tokens = api.token("user@example.com", "Super-Strong-Pass-123!")
    assert isinstance(tokens.access_token, str)
    assert isinstance(tokens.refresh_token, str)

    refreshed = TokenPairResponse.model_validate(api.try_refresh(tokens.refresh_token).json())
    assert isinstance(refreshed.access_token, str)
    assert isinstance(refreshed.refresh_token, str)

    api.set_access_token(tokens.access_token)
    out = api.try_logout(tokens.access_token)
    assert out.status_code == 204, out.text

    bad = api.try_refresh(refreshed.refresh_token)
    assert bad.status_code == 400, bad.text


def test_signup_duplicate_email_rejected(api: ApiClient) -> None:
    r = api.try_signup("user@example.com", "Super-Strong-Pass-123!")
    assert r.status_code == 400, r.text


def test_login_invalid_credentials(api: ApiClient) -> None:
    r = api.try_token("user@example.com", "wrong-password-!!!")
    assert r.status_code == 400, r.text


def test_login_unknown_email(api: ApiClient) -> None:
    r = api.try_token("nobody@example.com", "Super-Strong-Pass-123!")
    assert r.status_code == 400, r.text


def test_refresh_with_invalid_token(api: ApiClient) -> None:
    r = api.try_refresh("not.a.real.token")
    assert r.status_code == 400, r.text


def test_refresh_token_reuse_rejected(api: ApiClient) -> None:
    """A refresh token must be single-use; reusing it after a successful refresh must fail."""
    tokens = api.token("user@example.com", "Super-Strong-Pass-123!")

    # First refresh — must succeed
    r1 = api.try_refresh(tokens.refresh_token)
    assert r1.status_code == 200, r1.text

    # Second refresh with the same original token — must fail (revoked)
    r2 = api.try_refresh(tokens.refresh_token)
    assert r2.status_code == 400, r2.text


def test_update_me_name_only(api: ApiClient) -> None:
    r = api.try_update_me(name="Alice")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Alice"
    assert body["email"] == "user@example.com"


def test_update_me_email_requires_current_password(api: ApiClient) -> None:
    r = api.try_update_me(email="new@example.com")
    assert r.status_code == 400, r.text


def test_update_me_email_wrong_current_password(api: ApiClient) -> None:
    r = api.try_update_me(email="new@example.com", current_password="wrong-password-!!")
    assert r.status_code == 400, r.text


def test_update_me_email_success(api: ApiClient) -> None:
    r = api.try_update_me(
        email="updated@example.com",
        current_password="Super-Strong-Pass-123!",
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "updated@example.com"


def test_update_me_email_already_in_use(api: ApiClient) -> None:
    # Register a second user
    api.signup("other@example.com", "Super-Strong-Pass-123!")

    # Try to change the first user's email to the second user's email
    r = api.try_update_me(
        email="other@example.com",
        current_password="Super-Strong-Pass-123!",
    )
    assert r.status_code == 400, r.text


def test_update_me_password_success(api: ApiClient) -> None:
    r = api.try_update_me(
        new_password="Brand-New-Pass-456!",
        current_password="Super-Strong-Pass-123!",
    )
    assert r.status_code == 200, r.text

    # Old password must no longer work
    bad = api.try_token("user@example.com", "Super-Strong-Pass-123!")
    assert bad.status_code == 400, bad.text

    # New password must work
    good = api.try_token("user@example.com", "Brand-New-Pass-456!")
    assert good.status_code == 200, good.text


def test_update_me_new_password_requires_current_password(api: ApiClient) -> None:
    r = api.try_update_me(new_password="Brand-New-Pass-456!")
    assert r.status_code == 400, r.text


def test_update_me_same_email_no_op(api: ApiClient) -> None:
    """Submitting the same email with correct current_password should succeed silently."""
    r = api.try_update_me(
        email="user@example.com",
        current_password="Super-Strong-Pass-123!",
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "user@example.com"


def test_me_unauthenticated(api: ApiClient) -> None:
    r = api.try_me(use_auth=False)
    assert r.status_code == 401, r.text
