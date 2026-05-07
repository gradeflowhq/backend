import uuid

import valkey
from pydantic import JsonValue
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.config import get_settings
from gradeflow_backend.models import Assessment
from gradeflow_backend.utils.datetime import utcnow

from .base import BaseRepository


class AssessmentRepository(BaseRepository):
    def __init__(self, session: Session, valkey_client: valkey.Valkey | None = None) -> None:
        super().__init__(session)
        self._valkey = valkey_client

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, name: str, description: str | None) -> Assessment:
        a = Assessment(id=uuid.uuid4().hex, name=name, description=description)
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

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, id: str) -> dict[str, JsonValue]:
        a = self.get(id)
        return dict(a.metadata_json or {})

    def replace_metadata(self, id: str, metadata: dict[str, JsonValue]) -> dict[str, JsonValue]:
        a = self.get(id)
        a.metadata_json = dict(metadata)
        self.session().flush()
        return dict(a.metadata_json or {})

    def set_metadata_value(self, id: str, key: str, value: JsonValue) -> dict[str, JsonValue]:
        a = self.get(id)
        metadata = dict(a.metadata_json or {})
        metadata[key] = value
        a.metadata_json = metadata
        self.session().flush()
        return dict(a.metadata_json or {})

    def delete_metadata_value(self, id: str, key: str) -> None:
        a = self.get(id)
        metadata = dict(a.metadata_json or {})
        if key not in metadata:
            return
        del metadata[key]
        a.metadata_json = metadata
        self.session().flush()

    # ------------------------------------------------------------------
    # YAML blob setters / getters
    # ------------------------------------------------------------------

    def set_question_set_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.question_set_yaml = yaml_str
        a.question_set_updated_at = utcnow()
        self.session().flush()

    def get_question_set_yaml(self, id: str) -> str | None:
        return self.get(id).question_set_yaml

    def set_rubric_yaml(self, id: str, yaml_str: str | None) -> None:
        a = self.get(id)
        a.rubric_yaml = yaml_str
        a.rubric_updated_at = utcnow()
        self.session().flush()

    def get_rubric_yaml(self, id: str) -> str | None:
        return self.get(id).rubric_yaml

    def set_source(self, id: str, data: str | None, student_id_column: str | None) -> None:
        a = self.get(id)
        a.source_data = data
        a.source_student_id_column = student_id_column
        a.source_updated_at = utcnow()
        self.session().flush()

    def get_source_data(self, id: str) -> str | None:
        return self.get(id).source_data

    def get_source_student_id_column(self, id: str) -> str | None:
        return self.get(id).source_student_id_column

    def set_submissions_config_yaml(self, id: str, data: str | None) -> None:
        a = self.get(id)
        a.submissions_config_yaml = data
        a.source_updated_at = utcnow()
        self.session().flush()

    def get_submissions_config_yaml(self, id: str) -> str | None:
        return self.get(id).submissions_config_yaml

    def stamp_results_updated_at(self, id: str) -> None:
        """Stamp results_updated_at after a successful grading run."""
        a = self.get(id)
        a.results_updated_at = utcnow()
        self.session().flush()

    # ------------------------------------------------------------------
    # Preview (Valkey)
    # ------------------------------------------------------------------

    @staticmethod
    def _preview_key(assessment_id: str) -> str:
        return f"preview:{assessment_id}"

    def _require_valkey(self) -> valkey.Valkey:
        if self._valkey is None:
            raise RuntimeError("Valkey client required for preview operations")
        return self._valkey

    def set_preview_yaml(self, assessment_id: str, yaml_str: str | None) -> None:
        client = self._require_valkey()
        key = self._preview_key(assessment_id)
        if yaml_str is None:
            client.delete(key)
        else:
            client.set(key, yaml_str, ex=get_settings().valkey.preview_ttl_s)

    def get_preview_yaml(self, assessment_id: str) -> str | None:
        client = self._require_valkey()
        key = self._preview_key(assessment_id)
        val = client.get(key)
        return str(val) if val is not None else None
