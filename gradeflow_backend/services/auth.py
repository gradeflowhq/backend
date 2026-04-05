import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models.user import User
from gradeflow_backend.repositories.tokens import RefreshTokenRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenPairResponse,
    UpdateMeRequest,
)
from gradeflow_backend.security.jwt import (
    JwtError,
    assert_token_type,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from gradeflow_backend.security.passwords import hash_password, needs_rehash, verify_password
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.utils.datetime import utcnow


def _user_to_me(u: User) -> MeResponse:
    return MeResponse(id=u.id, email=u.email, name=u.name)


class AuthService:
    def __init__(self, users: UserRepository, tokens: RefreshTokenRepository) -> None:
        self._users = users
        self._tokens = tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def signup(self, req: SignupRequest) -> TokenPairResponse:
        if self._users.get_by_email(req.email):
            raise BadRequestError("Email already registered")

        user_id = uuid.uuid4().hex
        u = self._users.create(user_id, req.email, req.name, hash_password(req.password))
        return self._issue_token_pair(u.id)

    def login(self, req: LoginRequest) -> TokenPairResponse:
        u = self._users.get_by_email(req.email)
        if not u or not verify_password(req.password, u.password_hash):
            raise BadRequestError("Invalid credentials")

        if needs_rehash(u.password_hash):
            u.password_hash = hash_password(req.password)

        return self._issue_token_pair(u.id)

    def refresh(self, req: RefreshRequest) -> TokenPairResponse:
        user_id, jti = self._decode_refresh_token(req.refresh_token)

        if not self._tokens.is_valid(jti, utcnow()):
            raise BadRequestError("Refresh token expired or revoked")

        self._tokens.revoke(jti)
        return self._issue_token_pair(user_id)

    def logout(self, user_id: str) -> None:
        self._tokens.delete_user_tokens(user_id)

    def me(self, user_id: str) -> MeResponse:
        return _user_to_me(self._get_user_or_404(user_id))

    def update_me(self, user_id: str, req: UpdateMeRequest) -> MeResponse:
        u = self._get_user_or_404(user_id)
        self._verify_sensitive_change(req, u)

        u = self._users.update(
            user_id,
            email=self._resolve_new_email(req, u, user_id),
            name=req.name,
            password_hash=self._resolve_new_password_hash(req),
        )
        return _user_to_me(u)

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _issue_token_pair(self, user_id: str) -> TokenPairResponse:
        """
        Mint a fresh access + refresh token pair, persist the refresh token's
        JTI, and return the response schema.
        """
        access = create_access_token(sub=user_id)
        refresh = create_refresh_token(sub=user_id)

        payload = decode_token(refresh)
        assert_token_type(payload, "refresh")

        self._tokens.create(
            jti=str(payload["jti"]),
            user_id=user_id,
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )
        return TokenPairResponse(access_token=access, refresh_token=refresh)

    def _decode_refresh_token(self, token: str) -> tuple[str, str]:
        """
        Decode and validate a refresh token string.
        Returns (user_id, jti) or raises BadRequestError.
        """
        try:
            payload = decode_token(token)
            assert_token_type(payload, "refresh")
        except JwtError as e:
            raise BadRequestError("Invalid refresh token") from e

        user_id = str(payload.get("sub") or "")
        jti = str(payload.get("jti") or "")
        if not user_id or not jti:
            raise BadRequestError("Invalid refresh token")

        return user_id, jti

    # ------------------------------------------------------------------
    # User helpers
    # ------------------------------------------------------------------

    def _get_user_or_404(self, user_id: str) -> User:
        try:
            return self._users.get(user_id)
        except NoResultFound as e:
            raise NotFoundError("User not found") from e

    def _verify_sensitive_change(self, req: UpdateMeRequest, u: User) -> None:
        """
        Raise BadRequestError if the request touches email/password but
        current_password is absent or incorrect.
        """
        if req.email is None and req.new_password is None:
            return
        if not req.current_password:
            raise BadRequestError("current_password is required to change email or password")
        if not verify_password(req.current_password, u.password_hash):
            raise BadRequestError("current_password is incorrect")

    def _resolve_new_email(self, req: UpdateMeRequest, u: User, user_id: str) -> str | None:
        """
        Return the normalised new email if it differs from the current one,
        None if unchanged or not requested.
        """
        if req.email is None:
            return None

        normalised = req.email.strip().lower()
        if normalised == u.email.lower():
            return None  # no actual change — skip the update

        existing = self._users.get_by_email(normalised)
        if existing is not None and existing.id != user_id:
            raise BadRequestError("Email already in use")

        return normalised

    @staticmethod
    def _resolve_new_password_hash(req: UpdateMeRequest) -> str | None:
        """Return a freshly hashed password, or None if not being changed."""
        if req.new_password is None:
            return None
        return hash_password(req.new_password)
