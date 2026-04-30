from abc import ABC, abstractmethod
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from gradeflow_engine.io.sources import DataSource
from gradeflow_engine.serializations.base import DataBlob
from pydantic import BaseModel

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.utils.io import blob_from_str, source_from_data

ArtifactT = TypeVar("ArtifactT")
ResponseT = TypeVar("ResponseT")
ExportResponseT = TypeVar("ExportResponseT")


@runtime_checkable
class HasFormat(Protocol):
    format: str


@runtime_checkable
class HasName(Protocol):
    name: str


class YamlArtifactService(BaseService, ABC, Generic[ArtifactT, ResponseT, ExportResponseT]):
    def __init__(self, repo: AssessmentRepository) -> None:
        super().__init__(repo)

    def _set_by_model(self, assessment_id: str, artifact: ArtifactT) -> ResponseT:
        self._get_or_404(assessment_id)
        return self._store_and_respond(assessment_id, artifact)

    def _set_by_data(self, assessment_id: str, data: str, serializer: BaseModel) -> ResponseT:
        artifact = self._load_from_blob(
            blob_from_str(
                data,
                media_type="application/octet-stream",
                ext=self._serializer_name(serializer),
            ),
            serializer_name=self._serializer_name(serializer),
            serializer_kwargs=serializer.model_dump(exclude={"format"}),
        )
        return self._store_and_respond(assessment_id, artifact)

    def _set_by_adapter(
        self,
        assessment_id: str,
        data: str | bytes,
        adapter: BaseModel,
    ) -> ResponseT:
        artifact = self._load_via_adapter(
            source_from_data(data),
            adapter_name=self._adapter_name(adapter),
            adapter_kwargs=adapter.model_dump(exclude={"name"}),
        )
        return self._store_and_respond(assessment_id, artifact)

    def _get_response(self, assessment_id: str) -> ResponseT:
        assessment = self._get_or_404(assessment_id)
        return self._build_response(assessment, self._load_stored(assessment))

    def _export_artifact(self, assessment_id: str, serializer: BaseModel) -> ExportResponseT:
        assessment = self._get_or_404(assessment_id)
        artifact = self._load_stored(assessment)
        blob = self._dump_to_blob(
            artifact,
            serializer_name=self._serializer_name(serializer),
            serializer_kwargs=serializer.model_dump(exclude={"format"}),
        )
        return self._build_export_response(assessment, blob)

    def _delete_artifact(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self._store_yaml(assessment_id, None)

    def _store_and_respond(self, assessment_id: str, artifact: ArtifactT) -> ResponseT:
        blob = self._dump_to_blob(artifact, serializer_name="yaml")
        self._store_yaml(assessment_id, blob.data.decode("utf-8"))
        return self._build_response(self._get_or_404(assessment_id), artifact)

    def _serializer_name(self, serializer: BaseModel) -> str:
        if not isinstance(serializer, HasFormat):
            raise ValueError(f"Serializer {type(serializer).__name__} has no 'format' attribute")
        return serializer.format

    def _adapter_name(self, adapter: BaseModel) -> str:
        if not isinstance(adapter, HasName):
            raise ValueError(f"Adapter {type(adapter).__name__} has no 'name' attribute")
        return adapter.name

    @abstractmethod
    def _load_from_blob(
        self,
        blob: DataBlob,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> ArtifactT:
        raise NotImplementedError

    @abstractmethod
    def _load_via_adapter(
        self,
        source: DataSource,
        *,
        adapter_name: str,
        adapter_kwargs: dict[str, Any] | None = None,
    ) -> ArtifactT:
        raise NotImplementedError

    @abstractmethod
    def _load_stored(self, assessment: Assessment) -> ArtifactT:
        raise NotImplementedError

    @abstractmethod
    def _dump_to_blob(
        self,
        artifact: ArtifactT,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> DataBlob:
        raise NotImplementedError

    @abstractmethod
    def _store_yaml(self, assessment_id: str, yaml_str: str | None) -> None:
        raise NotImplementedError

    @abstractmethod
    def _build_response(self, assessment: Assessment, artifact: ArtifactT) -> ResponseT:
        raise NotImplementedError

    @abstractmethod
    def _build_export_response(
        self,
        assessment: Assessment,
        blob: DataBlob,
    ) -> ExportResponseT:
        raise NotImplementedError
