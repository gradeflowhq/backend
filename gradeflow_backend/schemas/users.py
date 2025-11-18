from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None


class UsersListResponse(BaseModel):
    items: list[UserResponse]


class UserAssessmentsResponse(BaseModel):
    # List of assessment IDs the user belongs to
    items: list[str]


class AssessmentUsersResponse(BaseModel):
    # List of users belonging to an assessment
    items: list[UserResponse]
