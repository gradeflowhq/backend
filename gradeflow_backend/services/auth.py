import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import NoResultFound

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
from gradeflow_backend.security.passwords import (
    hash_password,
    needs_rehash,
    verify_password,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError


class AuthService:
    def __init__(self, users: UserRepository, tokens: RefreshTokenRepository) -> None:
        self.users = users
        self.tokens = tokens

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def signup(self, req: SignupRequest) -> TokenPairResponse:
        if self.users.get_by_email(req.email):
            raise BadRequestError("Email already registered")
        user_id = uuid.uuid4().hex
        pwd_hash = hash_password(req.password)
        u = self.users.create(user_id, req.email, req.name, pwd_hash)

        # Issue tokens
        access = create_access_token(sub=u.id)
        refresh = create_refresh_token(sub=u.id)
        # Persist refresh token jti with expiry
        payload = decode_token(refresh)
        assert_token_type(payload, "refresh")
        jti = str(payload["jti"])
        exp_ts = int(payload["exp"])
        expires_at = datetime.fromtimestamp(exp_ts, tz=UTC)
        self.tokens.create(jti=jti, user_id=u.id, expires_at=expires_at)

        return TokenPairResponse(access_token=access, refresh_token=refresh)

    def login(self, req: LoginRequest) -> TokenPairResponse:
        u = self.users.get_by_email(req.email)
        if not u or not verify_password(req.password, u.password_hash):
            raise BadRequestError("Invalid credentials")
        # Optional: rehash if needed
        if needs_rehash(u.password_hash):
            u.password_hash = hash_password(req.password)

        access = create_access_token(sub=u.id)
        refresh = create_refresh_token(sub=u.id)
        payload = decode_token(refresh)
        assert_token_type(payload, "refresh")
        jti = str(payload["jti"])
        exp_ts = int(payload["exp"])
        expires_at = datetime.fromtimestamp(exp_ts, tz=UTC)
        self.tokens.create(jti=jti, user_id=u.id, expires_at=expires_at)

        return TokenPairResponse(access_token=access, refresh_token=refresh)

    def refresh(self, req: RefreshRequest) -> TokenPairResponse:
        try:
            payload = decode_token(req.refresh_token)
            assert_token_type(payload, "refresh")
        except JwtError as e:
            raise BadRequestError("Invalid refresh token") from e

        user_id = str(payload.get("sub") or "")
        jti = str(payload.get("jti") or "")
        if not user_id or not jti:
            raise BadRequestError("Invalid refresh token")

        # Check stored token validity and revoke it (rotation)
        now = self._now()
        if not self.tokens.is_valid(jti, now):
            raise BadRequestError("Refresh token expired or revoked")
        self.tokens.revoke(jti)

        # Issue new pair
        access = create_access_token(sub=user_id)
        refresh = create_refresh_token(sub=user_id)
        new_payload = decode_token(refresh)
        assert_token_type(new_payload, "refresh")
        new_jti = str(new_payload["jti"])
        exp_ts = int(new_payload["exp"])
        expires_at = datetime.fromtimestamp(exp_ts, tz=UTC)
        self.tokens.create(jti=new_jti, user_id=user_id, expires_at=expires_at)

        return TokenPairResponse(access_token=access, refresh_token=refresh)

    def logout(self, user_id: str) -> None:
        # Revoke all refresh tokens for the user
        self.tokens.delete_user_tokens(user_id)

    def me(self, user_id: str) -> MeResponse:
        try:
            u = self.users.get(user_id)
        except NoResultFound as e:
            raise NotFoundError("User not found") from e
        return MeResponse(id=u.id, email=u.email, name=u.name)

    def update_me(self, user_id: str, req: UpdateMeRequest) -> MeResponse:
        try:
            u = self.users.get(user_id)
        except NoResultFound as e:
            raise NotFoundError("User not found") from e

        # Sensitive changes (email or password) require current_password verification
        changing_sensitive = req.email is not None or req.new_password is not None
        if changing_sensitive:
            if not req.current_password:
                raise BadRequestError("current_password is required to change email or password")
            if not verify_password(req.current_password, u.password_hash):
                raise BadRequestError("current_password is incorrect")

        # Resolve fields to update
        new_email: str | None = None
        if req.email is not None:
            normalised = req.email.strip().lower()
            if normalised != u.email.lower():
                existing = self.users.get_by_email(normalised)
                if existing is not None and existing.id != user_id:
                    raise BadRequestError("Email already in use")
                new_email = normalised

        new_password_hash: str | None = None
        if req.new_password is not None:
            new_password_hash = hash_password(req.new_password)

        # name=None means "not provided / no change"; empty string is a valid name
        new_name: str | None = req.name  # passed through as-is; None -> no-op in repo

        u = self.users.update(
            user_id,
            email=new_email,
            name=new_name,
            password_hash=new_password_hash,
        )
        return MeResponse(id=u.id, email=u.email, name=u.name)
