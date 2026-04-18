from tests.helpers.api import ApiClient


def test_me_returns_user(api: ApiClient) -> None:
    """Authenticated /users/me returns the synced user from the DB."""
    me = api.me()
    assert me.email == "user@example.com"
    # id is now an internal UUID, not the IdP sub
    assert len(me.id) == 32  # uuid4().hex length


def test_me_unauthenticated(api: ApiClient) -> None:
    r = api.try_me(use_auth=False)
    assert r.status_code in (401, 403), r.text
