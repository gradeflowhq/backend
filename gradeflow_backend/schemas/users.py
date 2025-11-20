from pydantic import BaseModel, EmailStr

from gradeflow_backend.schemas.roles import Role


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    role: Role


class UsersListResponse(BaseModel):
    items: list[UserResponse]


class UserAssessmentsResponse(BaseModel):
    # List of assessment IDs the user belongs to
    items: list[str]


class AssessmentUsersResponse(BaseModel):
    # List of users belonging to an assessment
    items: list[UserResponse]
