from typing import cast

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models import Assessment, User, UserAssessment
from gradeflow_backend.schemas.roles import Role  # Literal["owner", "editor", "viewer"]

from .base import BaseRepository


class MembershipRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def is_member(self, user_id: str, assessment_id: str) -> bool:
        link = self.session().get(
            UserAssessment, {"user_id": user_id, "assessment_id": assessment_id}
        )
        return link is not None

    def add_member(self, user_id: str, assessment_id: str, role: Role = "viewer") -> None:
        if not self.is_member(user_id, assessment_id):
            link = UserAssessment(user_id=user_id, assessment_id=assessment_id, role=role)
            self.session().add(link)
            self.session().flush()

    def remove_member(self, user_id: str, assessment_id: str) -> None:
        link = self.session().get(
            UserAssessment, {"user_id": user_id, "assessment_id": assessment_id}
        )
        if link:
            self.session().delete(link)
            self.session().flush()

    def set_role(self, user_id: str, assessment_id: str, role: Role) -> None:
        link = self.session().get(
            UserAssessment, {"user_id": user_id, "assessment_id": assessment_id}
        )
        if link is None:
            link = UserAssessment(user_id=user_id, assessment_id=assessment_id, role=role)
            self.session().add(link)
        else:
            link.role = role
        self.session().flush()

    def get_role(self, user_id: str, assessment_id: str) -> Role | None:
        link = self.session().get(
            UserAssessment, {"user_id": user_id, "assessment_id": assessment_id}
        )
        if not link:
            return None
        # Validate string to match the Literal type
        if link.role in {"owner", "editor", "viewer"}:
            return cast(Role, link.role)
        return None

    def list_assessment_users(self, assessment_id: str) -> list[User]:
        a = self.session().get(Assessment, assessment_id)
        if not a:
            raise NoResultFound("Assessment not found")
        return list(a.users)  # association proxy yields iterable

    def list_user_assessments(self, user_id: str) -> list[Assessment]:
        u = self.session().get(User, user_id)
        if not u:
            raise NoResultFound("User not found")
        return list(u.assessments)

    def list_assessment_members_with_roles(self, assessment_id: str) -> list[tuple[User, Role]]:
        q = (
            self.session()
            .query(UserAssessment, User)
            .join(User, User.id == UserAssessment.user_id)
            .filter(UserAssessment.assessment_id == assessment_id)
            .all()
        )
        result: list[tuple[User, Role]] = []
        for link, user in q:
            role_str = link.role if link.role in {"owner", "editor", "viewer"} else "viewer"
            result.append((user, cast(Role, role_str)))
        return result
