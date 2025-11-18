from tests.helpers.api import ApiClient
from tests.helpers.data import ASSESSMENT_ID


def test_assessment_crud(api: ApiClient) -> None:
    # Create
    created = api.create_assessment(ASSESSMENT_ID, "Midterm", "Desc")
    assert created.id == ASSESSMENT_ID

    # List (requires auth)
    lst = api.list_assessments()
    assert any(item.id == ASSESSMENT_ID for item in lst.items)

    # Get (membership is granted to creator)
    got = api.get_assessment(ASSESSMENT_ID)
    assert got.id == ASSESSMENT_ID

    # Update (owner only)
    updated = api.update_assessment(ASSESSMENT_ID, name="Midterm 2")
    assert updated.name == "Midterm 2"

    # Delete (owner only)
    api.delete_assessment(ASSESSMENT_ID)
    lst = api.list_assessments()
    assert not any(item.id == ASSESSMENT_ID for item in lst.items)
