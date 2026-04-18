from tests.helpers.api import ApiClient


def test_memberships_owner_can_manage(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")

    viewer = api.create_other_user("viewer@example.com")
    viewer_id = viewer.me().id

    add_resp = api.add_member(created.id, user_email="viewer@example.com")
    assert add_resp.assessment_id == created.id
    assert add_resp.user_id == viewer_id
    assert add_resp.role == "viewer"

    set_resp = api.set_member_role(created.id, user_id=viewer_id, role="editor")
    assert set_resp.role == "editor"

    members = api.list_members(created.id)
    assert any(u.id == viewer_id for u in members.items)

    viewer_item = next(u for u in members.items if u.id == viewer_id)
    assert viewer_item.role == "editor"

    api.remove_member(created.id, user_id=viewer_id)

    members_after = api.list_members(created.id)
    assert not any(u.id == viewer_id for u in members_after.items)


def test_memberships_non_owner_blocked(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")

    other = api.create_other_user("other@example.com")
    other_id = other.me().id

    resp_add = other.try_add_member(created.id, user_email="other@example.com", role="viewer")
    assert resp_add.status_code == 403, resp_add.text

    resp_set = other.try_set_member_role(created.id, user_id=other_id, role="editor")
    assert resp_set.status_code == 403, resp_set.text

    resp_rm = other.try_remove_member(created.id, user_id=other_id)
    assert resp_rm.status_code == 403, resp_rm.text


def test_add_member_user_not_found(api: ApiClient) -> None:
    created = api.create_assessment("Ghost Member")
    r = api.try_add_member(created.id, user_email="doesnotexist@example.com")
    assert r.status_code == 404, r.text


def test_viewer_can_list_members(api: ApiClient) -> None:
    created = api.create_assessment("Viewer List")

    viewer = api.create_other_user("viewer_list@example.com")

    api.add_member(created.id, user_email="viewer_list@example.com", role="viewer")

    r = viewer.try_list_members(created.id)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 1


def test_add_member_with_explicit_role(api: ApiClient) -> None:
    api.create_other_user("editor_exp@example.com")
    created = api.create_assessment("Explicit Role")

    resp = api.add_member(created.id, user_email="editor_exp@example.com", role="editor")
    assert resp.role == "editor"

    members = api.list_members(created.id)
    added = next(u for u in members.items if u.email == "editor_exp@example.com")
    assert added.role == "editor"
