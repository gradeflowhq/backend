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
    # Get tokens via OAuth2
    tokens = api.token("user@example.com", "Super-Strong-Pass-123!")
    assert isinstance(tokens.access_token, str)
    assert isinstance(tokens.refresh_token, str)

    # Refresh
    resp = api.client.post("/auth/refresh", json={"refresh_token": tokens.refresh_token})
    assert resp.status_code == 200, resp.text
    refreshed = TokenPairResponse.model_validate(resp.json())
    assert isinstance(refreshed.access_token, str)
    assert isinstance(refreshed.refresh_token, str)

    # Logout revokes all refresh tokens
    api.set_access_token(tokens.access_token)
    out = api.client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {tokens.access_token}"}
    )
    assert out.status_code == 204, out.text

    # Refresh should fail now
    bad = api.client.post("/auth/refresh", json={"refresh_token": refreshed.refresh_token})
    assert bad.status_code == 400, bad.text
