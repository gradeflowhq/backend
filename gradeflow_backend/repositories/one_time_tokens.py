import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.models.one_time_token import OneTimeToken

from .base import BaseRepository


class OneTimeTokenRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def create(self) -> OneTimeToken:
        tok = uuid.uuid4().hex
        obj = OneTimeToken(token=tok)
        self.session().add(obj)
        self.session().flush()
        return obj

    def get(self, token: str) -> OneTimeToken:
        obj = self.session().get(OneTimeToken, token)
        if not obj:
            raise NoResultFound("One-time token not found")
        return obj

    def consume(self, token: str) -> None:
        obj = self.get(token)
        obj.consumed_at = datetime.now(UTC)
        self.session().flush()
