from sqlalchemy.orm import Session


class BaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def session(self) -> Session:
        return self._session
