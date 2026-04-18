from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models import User
from gradeflow_backend.models.user_identity import UserIdentity

from .base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # -----------------
    # Lookups
    # -----------------

    def find_by_identity(self, provider: str, provider_user_id: str) -> User | None:
        """Return the user linked to the given provider identity, or *None*."""
        identity = (
            self.session()
            .query(UserIdentity)
            .filter_by(provider=provider, provider_user_id=provider_user_id)
            .one_or_none()
        )
        return identity.user if identity else None

    # -----------------
    # CRUD
    # -----------------

    def upsert_from_token(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str,
        name: str | None,
    ) -> User:
        """
        Resolve or create a local User from an IdP token.

        Lookup order:
          1. (provider, provider_user_id) — fast path, normal login.
          2. email — migration path when sub changes but email is the same.
          3. Create new user + identity if neither matches.
        """
        # 1. Fast path: known identity
        identity = (
            self.session()
            .query(UserIdentity)
            .filter_by(provider=provider, provider_user_id=provider_user_id)
            .one_or_none()
        )
        if identity:
            self.sync_profile(identity.user, email=email, name=name)
            return identity.user

        # 2. Migration path: same email, new provider or rotated sub
        user = self.session().query(User).filter_by(email=email).one_or_none()
        if user:
            new_identity = UserIdentity(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
            )
            self.session().add(new_identity)
            self.sync_profile(user, email=email, name=name)
            self.session().flush()
            return user

        # 3. Brand new user
        user = User(email=email, name=name)
        self.session().add(user)
        self.session().flush()
        identity = UserIdentity(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        self.session().add(identity)
        self.session().flush()
        return user

    def sync_profile(self, user: User, email: str | None = None, name: str | None = None) -> None:
        """Update cached profile fields if they changed in the IdP."""
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if name is not None and user.name != name:
            user.name = name
            changed = True
        if changed:
            self.session().flush()

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
