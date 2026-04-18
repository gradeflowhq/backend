from fastapi import APIRouter, Depends

from gradeflow_backend.dependencies.auth import get_current_db_user
from gradeflow_backend.models.user import User
from gradeflow_backend.schemas.auth import MeResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_db_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, name=user.name)
