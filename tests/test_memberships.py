from gradeflow_backend.schemas.auth import TokenPairResponse
from tests.helpers.api import ApiClient


def test_memberships_owner_can_manage(api: ApiClient) -> None:
    # Owner creates assessment
    created = api.create_assessment("Midterm")

    # Create another user (viewer) and authenticate
    viewer = ApiClient(api.client)
    v_tokens: TokenPairResponse = viewer.signup("viewer@example.com", "Strong-Pass-12345!")
    viewer.set_access_token(v_tokens.access_token)
    viewer_id = viewer.me().id

    # Owner adds viewer as member (defaults to viewer if role omitted)
    add_resp = api.add_member(created.id, user_email="viewer@example.com")
    assert add_resp.assessment_id == created.id
    assert add_resp.user_id == viewer_id
    assert add_resp.role == "viewer"

    # Owner promotes viewer to editor
    set_resp = api.set_member_role(created.id, user_id=viewer_id, role="editor")
    assert set_resp.assessment_id == created.id
    assert set_resp.user_id == viewer_id
    assert set_resp.role == "editor"

    # Owner lists members; viewer should be present
    members = api.list_members(created.id)
    assert any(u.id == viewer_id for u in members.items)

    # Verify role reflected as editor
    viewer_item = next(u for u in members.items if u.id == viewer_id)
    assert viewer_item.role == "editor"

    # Owner removes viewer
    api.remove_member(created.id, user_id=viewer_id)

    # Verify removal
    members_after = api.list_members(created.id)
    assert not any(u.id == viewer_id for u in members_after.items)


def test_memberships_non_owner_blocked(api: ApiClient) -> None:
    # Owner creates assessment
    created = api.create_assessment("Midterm")

    # Another user (not an owner) authenticates
    other = ApiClient(api.client)
    o_tokens: TokenPairResponse = other.signup("other@example.com", "Strong-Pass-12345!")
    other.set_access_token(o_tokens.access_token)
    other_id = other.me().id  # retained for role/ removal tests below

    # Non-owner attempts to add a member → 403
    resp_add = other.try_add_member(created.id, user_email="other@example.com", role="viewer")
    assert resp_add.status_code == 403, resp_add.text

    # Non-owner attempts to set a role → 403
    resp_set = other.try_set_member_role(created.id, user_id=other_id, role="editor")
    assert resp_set.status_code == 403, resp_set.text

    # Non-owner attempts to remove a member → 403
    resp_rm = other.try_remove_member(created.id, user_id=other_id)
    assert resp_rm.status_code == 403, resp_rm.text
