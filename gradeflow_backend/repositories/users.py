from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models import User

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
