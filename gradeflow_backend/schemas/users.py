from pydantic import BaseModel, EmailStr

from gradeflow_backend.schemas.roles import Role


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    role: Role


class AssessmentUsersResponse(BaseModel):
    # List of users belonging to an assessment
    items: list[UserResponse]
