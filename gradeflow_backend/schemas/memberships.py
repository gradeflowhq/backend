from pydantic import BaseModel, EmailStr

from gradeflow_backend.schemas.roles import Role


class MembershipResponse(BaseModel):
    assessment_id: str
    user_id: str
    role: Role


class AddMemberRequest(BaseModel):
    user_email: EmailStr
    role: Role | None = None  # defaults applied in service/repository (e.g., "viewer")


class SetRoleRequest(BaseModel):
    role: Role
