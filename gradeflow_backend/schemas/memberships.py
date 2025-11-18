from pydantic import BaseModel

from gradeflow_backend.schemas.roles import Role


class MembershipResponse(BaseModel):
    assessment_id: str
    user_id: str


class AddMemberRequest(BaseModel):
    user_id: str
    role: Role | None = None  # defaults applied in service/repository (e.g., "viewer")


class SetRoleRequest(BaseModel):
    role: Role
