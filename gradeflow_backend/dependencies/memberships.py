from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.auth import get_current_user_id
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.schemas.roles import ROLE_ORDER, Role


def member_guard_factory() -> Callable[..., str]:
    """
    Returns a dependency that verifies the current user is a member of the given assessment.
    Usage in router: _u: str = Depends(member_guard_factory())
    """

    def dep(
        assessment_id: str,
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_session),
    ) -> str:
        repo = MembershipRepository(db)
        if not repo.is_member(user_id, assessment_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of assessment",
            )
        return user_id

    return dep


def role_guard_factory(min_role: Role) -> Callable[..., str]:
    """
    Returns a dependency that verifies the current user has at least min_role
    for the given assessment.
    Usage in router: _u: str = Depends(role_guard_factory("editor"))
    """

    def dep(
        assessment_id: str,
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_session),
    ) -> str:
        repo = MembershipRepository(db)
        role = repo.get_role(user_id, assessment_id)
        if role is None or ROLE_ORDER[role] < ROLE_ORDER[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {min_role}",
            )
        return user_id

    return dep
