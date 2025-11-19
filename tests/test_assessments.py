from tests.helpers.api import ApiClient


def test_assessment_crud(api: ApiClient) -> None:
    # Create
    created = api.create_assessment("Midterm", "Desc")
    assert created.id is not None

    # List (requires auth)
    lst = api.list_assessments()
    assert any(item.id == created.id for item in lst.items)

    # Get (membership is granted to creator)
    got = api.get_assessment(created.id)
    assert got.id == created.id

    # Update (owner only)
    updated = api.update_assessment(created.id, name="Midterm 2")
    assert updated.name == "Midterm 2"

    # Delete (owner only)
    api.delete_assessment(created.id)
    lst = api.list_assessments()
    assert not any(item.id == created.id for item in lst.items)
