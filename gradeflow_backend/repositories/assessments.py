from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models import Assessment

from .base import BaseRepository


class AssessmentRepository(BaseRepository):
    # CRUD
    def create(self, id: str, name: str, description: str | None) -> Assessment:
        a = Assessment(id=id, name=name, description=description)
        self.session().add(a)
        self.session().flush()
        return a

    def get(self, id: str) -> Assessment:
        a = self.session().get(Assessment, id)
        if not a:
            raise NoResultFound(f"Assessment {id} not found")
        return a

    def list(self) -> list[Assessment]:
        return list(self.session().query(Assessment).order_by(Assessment.created_at.desc()).all())

    def update(self, id: str, name: str | None, description: str | None) -> Assessment:
        a = self.get(id)
        if name is not None:
            a.name = name
        if description is not None:
            a.description = description
        self.session().flush()
        return a

    def delete(self, id: str) -> None:
        a = self.get(id)
        self.session().delete(a)
        self.session().flush()

    # State setters/getters (JSON blobs)
    def set_question_set_json(self, id: str, json_str: str | None) -> None:
        a = self.get(id)
        a.question_set_json = json_str
        self.session().flush()

    def get_question_set_json(self, id: str) -> str | None:
        return self.get(id).question_set_json

    def set_rubric_json(self, id: str, json_str: str | None) -> None:
        a = self.get(id)
        a.rubric_json = json_str
        self.session().flush()

    def get_rubric_json(self, id: str) -> str | None:
        return self.get(id).rubric_json

    def set_submissions_json(self, id: str, json_str: str | None) -> None:
        a = self.get(id)
        a.submissions_json = json_str
        self.session().flush()

    def get_submissions_json(self, id: str) -> str | None:
        return self.get(id).submissions_json

    def set_graded_json(self, id: str, json_str: str | None) -> None:
        a = self.get(id)
        a.graded_json = json_str
        self.session().flush()

    def get_graded_json(self, id: str) -> str | None:
        return self.get(id).graded_json
