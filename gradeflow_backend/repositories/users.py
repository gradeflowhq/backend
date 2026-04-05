import builtins

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models import Assessment, User

from .base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # -----------------
    # CRUD
    # -----------------

    def create(self, id: str, email: str, name: str | None, password_hash: str) -> User:
        """
        Create a new user. Assumes email uniqueness is enforced at service layer and DB.
        """
        u = User(id=id, email=email, name=name, password_hash=password_hash)
        self.session().add(u)
        self.session().flush()
        return u

    def update(
        self,
        id: str,
        *,
        email: str | None = None,
        name: str | None = None,
        password_hash: str | None = None,
    ) -> User:
        """
        Partially update a user. Only non-None fields are applied.
        Raises NoResultFound if the user does not exist.
        """
        u = self.get(id)
        if email is not None:
            u.email = email
        if name is not None:
            u.name = name
        if password_hash is not None:
            u.password_hash = password_hash
        self.session().flush()
        return u

    def get(self, id: str) -> User:
        """
        Get a user by ID or raise NoResultFound.
        """
        u = self.session().get(User, id)
        if not u:
            raise NoResultFound("User not found")
        return u

    def get_by_email(self, email: str) -> User | None:
        """
        Return a user by email or None.
        """
        return self.session().query(User).filter(User.email == email).one_or_none()

    def list(self) -> list[User]:
        """
        List users, newest first.
        """
        return list(self.session().query(User).order_by(User.created_at.desc()).all())

    def delete(self, id: str) -> None:
        """
        Delete a user by ID. Raises NoResultFound if missing.
        """
        u = self.get(id)
        self.session().delete(u)
        self.session().flush()

    # -----------------
    # Membership (User ↔ Assessment)
    # -----------------

    def add_user_to_assessment(self, user_id: str, assessment_id: str) -> None:
        """
        Add membership; idempotent (won’t duplicate).
        """
        u = self.get(user_id)
        a = self.session().get(Assessment, assessment_id)
        if not a:
            raise NoResultFound("Assessment not found")
        if a not in u.assessments:
            u.assessments.append(a)
        self.session().flush()

    def remove_user_from_assessment(self, user_id: str, assessment_id: str) -> None:
        """
        Remove membership; idempotent (no error if not present).
        """
        u = self.get(user_id)
        a = self.session().get(Assessment, assessment_id)
        if not a:
            raise NoResultFound("Assessment not found")
        if a in u.assessments:
            u.assessments.remove(a)
        self.session().flush()

    def list_assessment_users(self, assessment_id: str) -> builtins.list[User]:
        """
        List users for a given assessment.
        """
        a = self.session().get(Assessment, assessment_id)
        if not a:
            raise NoResultFound("Assessment not found")
        # Relationship is configured with lazy="selectin" for efficient loading
        return a.users

    def list_user_assessments(self, user_id: str) -> builtins.list[Assessment]:
        """
        List assessments for a given user.
        """
        u = self.get(user_id)
        return u.assessments
