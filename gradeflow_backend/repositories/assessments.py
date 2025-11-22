import uuid

from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models import Assessment

from .base import BaseRepository


class AssessmentRepository(BaseRepository):
    # CRUD
    def create(self, name: str, description: str | None) -> Assessment:
        _id = uuid.uuid4().hex
        a = Assessment(id=_id, name=name, description=description)
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
    def set_question_set_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.question_set_yaml = yaml_str
        self.session().flush()

    def get_question_set_yaml(self, id: str) -> str | None:
        return self.get(id).question_set_yaml

    def set_rubric_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.rubric_yaml = yaml_str
        self.session().flush()

    def get_rubric_yaml(self, id: str) -> str | None:
        return self.get(id).rubric_yaml

    def set_submissions_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.submissions_yaml = yaml_str
        self.session().flush()

    def get_submissions_yaml(self, id: str) -> str | None:
        return self.get(id).submissions_yaml

    def set_graded_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.graded_submissions_yaml = yaml_str
        self.session().flush()

    def get_graded_yaml(self, id: str) -> str | None:
        return self.get(id).graded_submissions_yaml
