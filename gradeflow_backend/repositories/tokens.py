from datetime import datetime

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models import RefreshToken
from gradeflow_backend.utils.datetime import ensure_utc

from .base import BaseRepository


class RefreshTokenRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def create(self, jti: str, user_id: str, expires_at: datetime) -> RefreshToken:
        rt = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
        self.session().add(rt)
        self.session().flush()
        return rt

    def get(self, jti: str) -> RefreshToken:
        rt = self.session().get(RefreshToken, jti)
        if not rt:
            raise NoResultFound("Refresh token not found")
        return rt

    def revoke(self, jti: str) -> None:
        rt = self.get(jti)
        if not rt.revoked:
            rt.revoked = True
            self.session().flush()

    def is_valid(self, jti: str, now: datetime) -> bool:
        rt = self.session().get(RefreshToken, jti)
        if not rt or rt.revoked:
            return False
        return ensure_utc(rt.expires_at) > ensure_utc(now)

    def delete_user_tokens(self, user_id: str) -> None:
        self.session().query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        self.session().flush()
