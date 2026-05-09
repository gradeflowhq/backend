from typing import TypeAlias

from fastapi.testclient import TestClient
from httpx import Response

from gradeflow_backend.schemas.assessments import (
    AssessmentMetadataResponse,
    AssessmentMetadataValueResponse,
    AssessmentResponse,
    AssessmentsListResponse,
)
from gradeflow_backend.schemas.auth import MeResponse
from gradeflow_backend.schemas.grading import (
    GradingDownloadResponse,
    GradingJob,
    GradingResponse,
    JobStatusResponse,
)
from gradeflow_backend.schemas.memberships import MembershipResponse
from gradeflow_backend.schemas.question_sets import (
    ExportQuestionSetResponse,
    ParseSubmissionsResponse,
    QuestionSetResponse,
    QuestionSetStatusResponse,
)
from gradeflow_backend.schemas.roles import Role
from gradeflow_backend.schemas.rubrics import (
    ExportRubricResponse,
    RubricOverviewResponse,
    RubricResponse,
    ValidateRubricResponse,
)
from gradeflow_backend.schemas.submissions import SubmissionsResponse
from gradeflow_backend.schemas.users import AssessmentUsersResponse

Headers: TypeAlias = dict[str, str]

_user_counter = 0


def _next_user_id() -> str:
    global _user_counter
    _user_counter += 1
    return f"test-user-{_user_counter}"


class ApiClient:
    def __init__(self, client: TestClient) -> None:
        self.client: TestClient = client
        self._auth_header: Headers = {}

    def set_access_token(self, access_token: str) -> None:
        self._auth_header = {"Authorization": f"Bearer {access_token}"}

    def create_other_user(self, email: str, name: str | None = None) -> "ApiClient":
        """
        Create a secondary authenticated API client backed by a different test user.
        Registers a new test identity in the auth override and syncs it to the DB
        via /users/me.
        """
        from tests.fixtures.client import register_test_user

        sub = _next_user_id()
        token = f"token-{sub}"
        register_test_user(token, sub=sub, email=email, name=name)
        other = ApiClient(self.client)
        other.set_access_token(token)
        # Hit /users/me to ensure the user row is created in the DB
        other.me()
        return other

    # -----------------
    # Users / Me
    # -----------------

    def try_me(self, use_auth: bool = True) -> Response:
        headers = self._auth_header if use_auth else {}
        return self.client.get("/users/me", headers=headers)

    def me(self) -> MeResponse:
        r = self.try_me()
        assert r.status_code == 200, r.text
        return MeResponse.model_validate(r.json())

    # -----------------
    # Health and registry
    # -----------------

    def try_get_health(self) -> Response:
        return self.client.get("/health")

    def try_get_registry_serializers(self, kind: str) -> Response:
        return self.client.get(f"/registry/serializers/{kind}")

    def try_get_registry_adapters(self, kind: str) -> Response:
        return self.client.get(f"/registry/adapters/{kind}")

    # -----------------
    # Assessments (try-variants)
    # -----------------

    def try_create_assessment(self, name: str, description: str | None = None) -> Response:
        return self.client.post(
            "/assessments",
            json={"name": name, "description": description},
            headers=self._auth_header,
        )

    def try_list_assessments(self) -> Response:
        return self.client.get("/assessments", headers=self._auth_header)

    def try_get_assessment(self, id: str) -> Response:
        return self.client.get(f"/assessments/{id}", headers=self._auth_header)

    def try_update_assessment(
        self,
        id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Response:
        return self.client.patch(
            f"/assessments/{id}",
            json={"name": name, "description": description},
            headers=self._auth_header,
        )

    def try_delete_assessment(self, id: str) -> Response:
        return self.client.delete(f"/assessments/{id}", headers=self._auth_header)

    def try_get_assessment_metadata(self, id: str) -> Response:
        return self.client.get(f"/assessments/{id}/metadata", headers=self._auth_header)

    def try_replace_assessment_metadata(self, id: str, metadata: dict[str, object]) -> Response:
        return self.client.put(
            f"/assessments/{id}/metadata",
            json={"metadata": metadata},
            headers=self._auth_header,
        )

    def try_get_assessment_metadata_value(self, id: str, key: str) -> Response:
        return self.client.get(
            f"/assessments/{id}/metadata/{key}",
            headers=self._auth_header,
        )

    def try_set_assessment_metadata_value(self, id: str, key: str, value: object) -> Response:
        return self.client.put(
            f"/assessments/{id}/metadata/{key}",
            json={"value": value},
            headers=self._auth_header,
        )

    def try_delete_assessment_metadata_value(self, id: str, key: str) -> Response:
        return self.client.delete(
            f"/assessments/{id}/metadata/{key}",
            headers=self._auth_header,
        )

    # Assessments (success-path delegates to try-)

    def create_assessment(self, name: str, description: str | None = None) -> AssessmentResponse:
        r = self.try_create_assessment(name=name, description=description)
        assert r.status_code == 201, r.text
        return AssessmentResponse.model_validate(r.json())

    def list_assessments(self) -> AssessmentsListResponse:
        r = self.try_list_assessments()
        assert r.status_code == 200, r.text
        return AssessmentsListResponse.model_validate(r.json())

    def get_assessment(self, id: str) -> AssessmentResponse:
        r = self.try_get_assessment(id=id)
        assert r.status_code == 200, r.text
        return AssessmentResponse.model_validate(r.json())

    def update_assessment(
        self,
        id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> AssessmentResponse:
        r = self.try_update_assessment(id=id, name=name, description=description)
        assert r.status_code == 200, r.text
        return AssessmentResponse.model_validate(r.json())

    def delete_assessment(self, id: str) -> None:
        r = self.try_delete_assessment(id=id)
        assert r.status_code == 204, r.text

    def get_assessment_metadata(self, id: str) -> AssessmentMetadataResponse:
        r = self.try_get_assessment_metadata(id=id)
        assert r.status_code == 200, r.text
        return AssessmentMetadataResponse.model_validate(r.json())

    def replace_assessment_metadata(
        self, id: str, metadata: dict[str, object]
    ) -> AssessmentMetadataResponse:
        r = self.try_replace_assessment_metadata(id=id, metadata=metadata)
        assert r.status_code == 200, r.text
        return AssessmentMetadataResponse.model_validate(r.json())

    def get_assessment_metadata_value(self, id: str, key: str) -> AssessmentMetadataValueResponse:
        r = self.try_get_assessment_metadata_value(id=id, key=key)
        assert r.status_code == 200, r.text
        return AssessmentMetadataValueResponse.model_validate(r.json())

    def set_assessment_metadata_value(
        self, id: str, key: str, value: object
    ) -> AssessmentMetadataValueResponse:
        r = self.try_set_assessment_metadata_value(id=id, key=key, value=value)
        assert r.status_code == 200, r.text
        return AssessmentMetadataValueResponse.model_validate(r.json())

    def delete_assessment_metadata_value(self, id: str, key: str) -> None:
        r = self.try_delete_assessment_metadata_value(id=id, key=key)
        assert r.status_code == 204, r.text

    # -----------------
    # Question sets (try-variants)
    # -----------------

    def try_set_question_set_yaml(self, assessment_id: str, yaml_str: str) -> Response:
        # Serializer-based upload
        return self.client.put(
            f"/assessments/{assessment_id}/question-set/upload",
            json={"data": yaml_str, "serializer": {"format": "yaml"}},
            headers=self._auth_header,
        )

    def try_import_question_set(
        self, assessment_id: str, *, data: str, adapter: dict[str, object]
    ) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/question-set/import",
            json={"data": data, "adapter": adapter},
            headers=self._auth_header,
        )

    def try_get_question_set(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/question-set",
            headers=self._auth_header,
        )

    def try_get_question_set_status(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/question-set/status",
            headers=self._auth_header,
        )

    def try_sync_question_set(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/question-set/sync",
            headers=self._auth_header,
        )

    def try_acknowledge_question_set_staleness(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/question-set/staleness/acknowledge",
            headers=self._auth_header,
        )

    def try_delete_question_set(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/question-set",
            headers=self._auth_header,
        )

    def try_parse_submissions(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/question-set/parse",
            json={},
            headers=self._auth_header,
        )

    def try_export_question_set(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/question-set/export",
            json={"serializer": {"format": "yaml"}},
            headers=self._auth_header,
        )

    def try_create_question(
        self,
        assessment_id: str,
        question_id: str,
        question: dict[str, object],
    ) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/question-set/questions",
            json={"question_id": question_id, "question": question},
            headers=self._auth_header,
        )

    def try_get_question(self, assessment_id: str, question_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/question-set/questions/{question_id}",
            headers=self._auth_header,
        )

    def try_update_question(
        self,
        assessment_id: str,
        question_id: str,
        question: dict[str, object],
    ) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/question-set/questions/{question_id}",
            json={"question": question},
            headers=self._auth_header,
        )

    def try_delete_question(self, assessment_id: str, question_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/question-set/questions/{question_id}",
            headers=self._auth_header,
        )

    # Question sets (success-path delegates to try-)

    def set_question_set_yaml(self, assessment_id: str, yaml_str: str) -> QuestionSetResponse:
        r = self.try_set_question_set_yaml(assessment_id=assessment_id, yaml_str=yaml_str)
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def import_question_set(
        self, assessment_id: str, *, data: str, adapter: dict[str, object]
    ) -> QuestionSetResponse:
        r = self.try_import_question_set(assessment_id=assessment_id, data=data, adapter=adapter)
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def get_question_set(self, assessment_id: str) -> QuestionSetResponse:
        r = self.try_get_question_set(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def get_question_set_status(self, assessment_id: str) -> QuestionSetStatusResponse:
        r = self.try_get_question_set_status(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return QuestionSetStatusResponse.model_validate(r.json())

    def sync_question_set(self, assessment_id: str) -> QuestionSetResponse:
        r = self.try_sync_question_set(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def acknowledge_question_set_staleness(self, assessment_id: str) -> QuestionSetResponse:
        r = self.try_acknowledge_question_set_staleness(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def delete_question_set(self, assessment_id: str) -> None:
        r = self.try_delete_question_set(assessment_id=assessment_id)
        assert r.status_code == 204, r.text

    def parse_submissions(self, assessment_id: str) -> ParseSubmissionsResponse:
        r = self.try_parse_submissions(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return ParseSubmissionsResponse.model_validate(r.json())

    def export_question_set(self, assessment_id: str) -> ExportQuestionSetResponse:
        r = self.try_export_question_set(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return ExportQuestionSetResponse.model_validate(r.json())

    def create_question(
        self,
        assessment_id: str,
        question_id: str,
        question: dict[str, object],
    ) -> QuestionSetResponse:
        r = self.try_create_question(
            assessment_id=assessment_id,
            question_id=question_id,
            question=question,
        )
        assert r.status_code == 201, r.text
        return QuestionSetResponse.model_validate(r.json())

    def update_question(
        self,
        assessment_id: str,
        question_id: str,
        question: dict[str, object],
    ) -> QuestionSetResponse:
        r = self.try_update_question(
            assessment_id=assessment_id,
            question_id=question_id,
            question=question,
        )
        assert r.status_code == 200, r.text
        return QuestionSetResponse.model_validate(r.json())

    def delete_question(self, assessment_id: str, question_id: str) -> None:
        r = self.try_delete_question(assessment_id=assessment_id, question_id=question_id)
        assert r.status_code == 204, r.text

    # -----------------
    # Rubrics (try-variants)
    # -----------------

    def try_set_rubric_yaml(self, assessment_id: str, yaml_str: str) -> Response:
        # Serializer-based upload
        return self.client.put(
            f"/assessments/{assessment_id}/rubric/upload",
            json={"data": yaml_str, "serializer": {"format": "yaml"}},
            headers=self._auth_header,
        )

    def try_import_rubric(
        self, assessment_id: str, *, data: str, adapter: dict[str, object]
    ) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/rubric/import",
            json={"data": data, "adapter": adapter},
            headers=self._auth_header,
        )

    def try_get_rubric(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/rubric",
            headers=self._auth_header,
        )

    def try_validate_rubric(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rubric/validate",
            json={},
            headers=self._auth_header,
        )

    def try_delete_rubric(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/rubric",
            headers=self._auth_header,
        )

    def try_export_rubric(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rubric/export",
            json={"serializer": {"format": "yaml"}},
            headers=self._auth_header,
        )

    def try_list_rules(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/rules",
            headers=self._auth_header,
        )

    def try_get_rule(self, assessment_id: str, rule_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/rules/{rule_id}",
            headers=self._auth_header,
        )

    def try_list_compatible_rules(
        self,
        assessment_id: str,
        *,
        question_id: str | None = None,
        path: str | None = None,
    ) -> Response:
        params: dict[str, str] = {}
        if question_id is not None:
            params["question_id"] = question_id
        if path is not None:
            params["path"] = path
        return self.client.get(
            f"/assessments/{assessment_id}/rules/list",
            params=params,
            headers=self._auth_header,
        )

    def try_get_rule_schema(
        self,
        assessment_id: str,
        *,
        rule_type: str,
        question_id: str | None = None,
        path: str | None = None,
    ) -> Response:
        params = {"type": rule_type}
        if question_id is not None:
            params["question_id"] = question_id
        if path is not None:
            params["path"] = path
        return self.client.get(
            f"/assessments/{assessment_id}/rules/schema",
            params=params,
            headers=self._auth_header,
        )

    def try_create_rule(self, assessment_id: str, rule: dict[str, object]) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rules",
            json={"rule": rule},
            headers=self._auth_header,
        )

    def try_update_rule(
        self,
        assessment_id: str,
        rule_id: str,
        rule: dict[str, object],
    ) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/rules/{rule_id}",
            json={"rule": rule},
            headers=self._auth_header,
        )

    def try_delete_rule(self, assessment_id: str, rule_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/rules/{rule_id}",
            headers=self._auth_header,
        )

    def try_acknowledge_rubric_staleness(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rubric/staleness/acknowledge",
            headers=self._auth_header,
        )

    def try_create_empty_rubric(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rubric/empty",
            headers=self._auth_header,
        )

    def try_sync_rubric(self, assessment_id: str) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/rubric/sync",
            headers=self._auth_header,
        )

    def try_get_rubric_overview(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/rubric/overview",
            headers=self._auth_header,
        )

    # Rubrics (success-path delegates to try-)

    def set_rubric_yaml(self, assessment_id: str, yaml_str: str) -> RubricResponse:
        r = self.try_set_rubric_yaml(assessment_id=assessment_id, yaml_str=yaml_str)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def create_rule(self, assessment_id: str, rule: dict[str, object]) -> RubricResponse:
        r = self.try_create_rule(assessment_id=assessment_id, rule=rule)
        assert r.status_code == 201, r.text
        return RubricResponse.model_validate(r.json())

    def update_rule(
        self,
        assessment_id: str,
        rule_id: str,
        rule: dict[str, object],
    ) -> RubricResponse:
        r = self.try_update_rule(assessment_id=assessment_id, rule_id=rule_id, rule=rule)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def delete_rule(self, assessment_id: str, rule_id: str) -> None:
        r = self.try_delete_rule(assessment_id=assessment_id, rule_id=rule_id)
        assert r.status_code == 204, r.text

    def acknowledge_rubric_staleness(self, assessment_id: str) -> RubricResponse:
        r = self.try_acknowledge_rubric_staleness(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def create_empty_rubric(self, assessment_id: str) -> RubricResponse:
        r = self.try_create_empty_rubric(assessment_id=assessment_id)
        assert r.status_code == 201, r.text
        return RubricResponse.model_validate(r.json())

    def sync_rubric(self, assessment_id: str) -> RubricResponse:
        r = self.try_sync_rubric(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def get_rubric_overview(self, assessment_id: str) -> RubricOverviewResponse:
        r = self.try_get_rubric_overview(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return RubricOverviewResponse.model_validate(r.json())

    def import_rubric(
        self, assessment_id: str, *, data: str, adapter: dict[str, object]
    ) -> RubricResponse:
        r = self.try_import_rubric(assessment_id=assessment_id, data=data, adapter=adapter)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def get_rubric(self, assessment_id: str) -> RubricResponse:
        r = self.try_get_rubric(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

    def validate_rubric(self, assessment_id: str) -> ValidateRubricResponse:
        r = self.try_validate_rubric(assessment_id=assessment_id)
        assert r.status_code in (200, 422), r.text
        return (
            ValidateRubricResponse.model_validate(r.json())
            if r.status_code == 200
            else ValidateRubricResponse(errors=[])
        )

    def delete_rubric(self, assessment_id: str) -> None:
        r = self.try_delete_rubric(assessment_id=assessment_id)
        assert r.status_code == 204, r.text

    def export_rubric(self, assessment_id: str) -> ExportRubricResponse:
        r = self.try_export_rubric(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return ExportRubricResponse.model_validate(r.json())

    # -----------------
    # Submissions (try-variants)
    # -----------------

    def try_upload_source_data(
        self, assessment_id: str, csv_str: str, student_id_column: str = "student_id"
    ) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/submissions/source",
            json={"data": csv_str, "student_id_column": student_id_column},
            headers=self._auth_header,
        )

    def try_get_source_data(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/submissions/source",
            headers=self._auth_header,
        )

    def try_save_submission_config(self, assessment_id: str, config: dict[str, object]) -> Response:
        return self.client.put(
            f"/assessments/{assessment_id}/submissions/config",
            json=config,
            headers=self._auth_header,
        )

    def try_get_submission_config(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/submissions/config",
            headers=self._auth_header,
        )

    def try_set_submissions_csv(self, assessment_id: str, csv_str: str) -> Response:
        r = self.try_upload_source_data(assessment_id, csv_str)
        if r.status_code != 200:
            return r
        return self.try_get_submissions(assessment_id)

    def try_get_submissions(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/submissions",
            headers=self._auth_header,
        )

    def try_delete_submissions(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/submissions",
            headers=self._auth_header,
        )

    # Submissions (success-path delegates to try-)

    def set_submissions_csv(self, assessment_id: str, csv_str: str) -> SubmissionsResponse:
        r = self.try_set_submissions_csv(assessment_id=assessment_id, csv_str=csv_str)
        assert r.status_code == 200, r.text
        return SubmissionsResponse.model_validate(r.json())

    def get_submissions(self, assessment_id: str) -> SubmissionsResponse:
        r = self.try_get_submissions(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return SubmissionsResponse.model_validate(r.json())

    def delete_submissions(self, assessment_id: str) -> None:
        r = self.try_delete_submissions(assessment_id=assessment_id)
        assert r.status_code == 204, r.text

    # -----------------
    # Grading
    # -----------------

    def try_run_grading(
        self, assessment_id: str, remove_adjustments: bool | None = None
    ) -> Response:
        payload: dict[str, object] = {}
        if remove_adjustments is not None:
            payload["remove_adjustments"] = remove_adjustments
        return self.client.post(
            f"/assessments/{assessment_id}/grading",
            json=payload,
            headers=self._auth_header,
        )

    def run_grading_start(self, assessment_id: str) -> GradingJob:
        r = self.try_run_grading(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return GradingJob.model_validate(r.json())

    def get_grading_job(self, assessment_id: str) -> GradingJob:
        r = self.client.get(
            f"/assessments/{assessment_id}/grading/job",
            headers=self._auth_header,
        )
        assert r.status_code == 200, r.text
        return GradingJob.model_validate(r.json())

    def try_get_job_status(self, job_id: str) -> Response:
        return self.client.get(f"/jobs/{job_id}")

    def get_job_status(self, job_id: str) -> JobStatusResponse:
        r = self.client.get(f"/jobs/{job_id}")
        assert r.status_code == 200, r.text
        return JobStatusResponse.model_validate(r.json())

    def try_get_grading(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/grading",
            headers=self._auth_header,
        )

    def get_grading(self, assessment_id: str) -> GradingResponse:
        r = self.try_get_grading(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return GradingResponse.model_validate(r.json())

    def try_download_grading(self, assessment_id: str) -> Response:
        # Download graded submissions (serializer-based)
        return self.client.post(
            f"/assessments/{assessment_id}/grading/download",
            json={"serializer": {"format": "csv"}},
            headers=self._auth_header,
        )

    def download_grading(self, assessment_id: str) -> GradingDownloadResponse:
        r = self.try_download_grading(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return GradingDownloadResponse.model_validate(r.json())

    def try_delete_grading(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/grading",
            headers=self._auth_header,
        )

    def delete_grading(self, assessment_id: str) -> None:
        r = self.try_delete_grading(assessment_id=assessment_id)
        assert r.status_code == 204, r.text

    def try_adjust_grading(self, assessment_id: str, adjustment: dict[str, object]) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/grading/adjust",
            json=adjustment,
            headers=self._auth_header,
        )

    def try_bulk_adjust(self, assessment_id: str, adjustments: list[dict[str, object]]) -> Response:
        return self.client.post(
            f"/assessments/{assessment_id}/grading/bulk-adjust",
            json={"adjustments": adjustments},
            headers=self._auth_header,
        )

    def try_get_grading_job(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/grading/job",
            headers=self._auth_header,
        )

    def try_cancel_grading_job(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/grading/job",
            headers=self._auth_header,
        )

    def try_cancel_preview_job(self, assessment_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/grading/preview/job",
            headers=self._auth_header,
        )

    def try_get_preview_job(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/grading/preview/job",
            headers=self._auth_header,
        )

    def try_callback(
        self,
        token: str,
        *,
        job_id: str = "job-test-callback-run",
        assessment_id: str,
        type: str,
        submissions: list[dict[str, object]] | None = None,
        remove_adjustments: bool = False,
    ) -> Response:
        payload: dict[str, object] = {
            "job_id": job_id,
            "assessment_id": assessment_id,
            "type": type,
            "remove_adjustments": remove_adjustments,
        }
        if submissions is not None:
            payload["submissions"] = submissions
        return self.client.post(f"/jobs/callback/{token}", json=payload)

    def adjust_grading(self, assessment_id: str, adjustment: dict[str, object]) -> GradingResponse:
        r = self.try_adjust_grading(assessment_id=assessment_id, adjustment=adjustment)
        assert r.status_code == 200, r.text
        return GradingResponse.model_validate(r.json())

    # Convenience helper to start run-grading and immediately fetch results
    def run_grading(self, assessment_id: str) -> GradingResponse:
        _ = self.run_grading_start(assessment_id)
        return self.get_grading(assessment_id)

    # -----------------
    # Grading preview
    # -----------------

    def try_preview_grading(
        self,
        assessment_id: str,
        *,
        rule: dict[str, object] | None = None,
        limit: int | None = None,
        selection: str | None = None,
        seed: int | None = None,
    ) -> Response:
        payload: dict[str, object] = {}
        if rule is not None:
            payload["rule"] = rule
        config: dict[str, object] = {}
        if limit is not None:
            config["limit"] = limit
        if selection is not None:
            config["selection"] = selection
        if seed is not None:
            config["seed"] = seed
        if config:
            payload["config"] = config

        return self.client.post(
            f"/assessments/{assessment_id}/grading/preview",
            json=payload,
            headers=self._auth_header,
        )

    def preview_grading_start(
        self,
        assessment_id: str,
        *,
        rule: dict[str, object] | None = None,
        limit: int | None = None,
        selection: str | None = None,
        seed: int | None = None,
    ) -> GradingJob:
        r = self.try_preview_grading(
            assessment_id=assessment_id,
            rule=rule,
            limit=limit,
            selection=selection,
            seed=seed,
        )
        assert r.status_code == 200, r.text
        return GradingJob.model_validate(r.json())

    def get_grading_preview(self, assessment_id: str) -> GradingResponse:
        r = self.client.get(
            f"/assessments/{assessment_id}/grading/preview",
            headers=self._auth_header,
        )
        assert r.status_code == 200, r.text
        return GradingResponse.model_validate(r.json())

    def preview_grading(
        self,
        assessment_id: str,
        *,
        rule: dict[str, object] | None = None,
        limit: int | None = None,
        selection: str | None = None,
        seed: int | None = None,
    ) -> GradingResponse:
        _ = self.preview_grading_start(
            assessment_id=assessment_id,
            rule=rule,
            limit=limit,
            selection=selection,
            seed=seed,
        )
        return self.get_grading_preview(assessment_id)

    # -----------------
    # Memberships (try-variants)
    # -----------------

    def try_list_members(self, assessment_id: str) -> Response:
        return self.client.get(
            f"/assessments/{assessment_id}/members",
            headers=self._auth_header,
        )

    def try_add_member(
        self,
        assessment_id: str,
        user_email: str,
        role: Role | None = None,
    ) -> Response:
        payload: dict[str, object] = {"user_email": user_email}
        if role is not None:
            payload["role"] = role
        return self.client.post(
            f"/assessments/{assessment_id}/members",
            json=payload,
            headers=self._auth_header,
        )

    def try_set_member_role(
        self,
        assessment_id: str,
        user_id: str,
        role: Role,
    ) -> Response:
        return self.client.patch(
            f"/assessments/{assessment_id}/members/{user_id}",
            json={"role": role},
            headers=self._auth_header,
        )

    def try_remove_member(self, assessment_id: str, user_id: str) -> Response:
        return self.client.delete(
            f"/assessments/{assessment_id}/members/{user_id}",
            headers=self._auth_header,
        )

    # Memberships (success-path delegates to try-)

    def list_members(self, assessment_id: str) -> AssessmentUsersResponse:
        r = self.try_list_members(assessment_id)
        assert r.status_code == 200, r.text
        return AssessmentUsersResponse.model_validate(r.json())

    def add_member(
        self,
        assessment_id: str,
        user_email: str,
        role: Role | None = None,
    ) -> MembershipResponse:
        r = self.try_add_member(assessment_id, user_email=user_email, role=role)
        assert r.status_code == 201, r.text
        return MembershipResponse.model_validate(r.json())

    def set_member_role(
        self,
        assessment_id: str,
        user_id: str,
        role: Role,
    ) -> MembershipResponse:
        r = self.try_set_member_role(assessment_id=assessment_id, user_id=user_id, role=role)
        assert r.status_code == 200, r.text
        return MembershipResponse.model_validate(r.json())

    def remove_member(self, assessment_id: str, user_id: str) -> None:
        r = self.try_remove_member(assessment_id=assessment_id, user_id=user_id)
        assert r.status_code == 204, r.text
