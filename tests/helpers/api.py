from typing import TypeAlias

from fastapi.testclient import TestClient
from httpx import Response

from gradeflow_backend.schemas.assessments import (
    AssessmentResponse,
    AssessmentsListResponse,
)
from gradeflow_backend.schemas.auth import MeResponse, TokenPairResponse
from gradeflow_backend.schemas.grading import (
    GradingDownloadResponse,
    GradingJob,
    GradingResponse,
    JobStatusResponse,
)
from gradeflow_backend.schemas.memberships import MembershipResponse
from gradeflow_backend.schemas.question_sets import (
    ParseSubmissionsResponse,
    QuestionSetResponse,
)
from gradeflow_backend.schemas.roles import Role
from gradeflow_backend.schemas.rubrics import (
    CoverageResponse,
    RubricResponse,
    ValidateRubricResponse,
)
from gradeflow_backend.schemas.submissions import SubmissionsResponse
from gradeflow_backend.schemas.users import AssessmentUsersResponse

Headers: TypeAlias = dict[str, str]


class ApiClient:
    def __init__(self, client: TestClient) -> None:
        self.client: TestClient = client
        self._auth_header: Headers = {}

    def set_access_token(self, access_token: str) -> None:
        self._auth_header = {"Authorization": f"Bearer {access_token}"}

    # -----------------
    # Auth (try-variants)
    # -----------------

    def try_signup(self, email: str, password: str, name: str | None = None) -> Response:
        return self.client.post(
            "/auth/signup",
            json={"email": email, "password": password, "name": name},
        )

    def try_token(self, email: str, password: str) -> Response:
        return self.client.post(
            "/auth/token",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def try_me(self) -> Response:
        return self.client.get("/auth/me", headers=self._auth_header)

    # Auth (success-path delegates to try-)

    def signup(self, email: str, password: str, name: str | None = None) -> TokenPairResponse:
        r = self.try_signup(email=email, password=password, name=name)
        assert r.status_code == 201, r.text
        return TokenPairResponse.model_validate(r.json())

    def token(self, email: str, password: str) -> TokenPairResponse:
        r = self.try_token(email=email, password=password)
        assert r.status_code == 200, r.text
        return TokenPairResponse.model_validate(r.json())

    def me(self) -> MeResponse:
        r = self.try_me()
        assert r.status_code == 200, r.text
        return MeResponse.model_validate(r.json())

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

    def delete_question_set(self, assessment_id: str) -> None:
        r = self.try_delete_question_set(assessment_id=assessment_id)
        assert r.status_code == 204, r.text

    def parse_submissions(self, assessment_id: str) -> ParseSubmissionsResponse:
        r = self.try_parse_submissions(assessment_id=assessment_id)
        assert r.status_code == 200, r.text
        return ParseSubmissionsResponse.model_validate(r.json())

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

    # Rubrics (success-path delegates to try-)

    def set_rubric_yaml(self, assessment_id: str, yaml_str: str) -> RubricResponse:
        r = self.try_set_rubric_yaml(assessment_id=assessment_id, yaml_str=yaml_str)
        assert r.status_code == 200, r.text
        return RubricResponse.model_validate(r.json())

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

    # -----------------
    # Rubrics Coverage (try-variants)
    # -----------------

    def try_rubric_coverage(
        self,
        assessment_id: str,
        *,
        use_stored_rubric: bool = True,
        use_stored_question_set: bool = True,
        rubric: dict[str, object] | None = None,
        question_set: dict[str, object] | None = None,
    ) -> Response:
        """
        Call coverage endpoint. By default uses stored rubric and question set.
        If use_stored_rubric/question_set are False, provide 'rubric' and/or 'question_set' dicts.
        """
        payload: dict[str, object] = {
            "use_stored_rubric": use_stored_rubric,
            "use_stored_question_set": use_stored_question_set,
        }
        if rubric is not None:
            payload["rubric"] = rubric
        if question_set is not None:
            payload["question_set"] = question_set

        return self.client.post(
            f"/assessments/{assessment_id}/rubric/coverage",
            json=payload,
            headers=self._auth_header,
        )

    # Rubrics Coverage (success-path delegates to try-)

    def rubric_coverage(
        self,
        assessment_id: str,
        *,
        use_stored_rubric: bool = True,
        use_stored_question_set: bool = True,
        rubric: dict[str, object] | None = None,
        question_set: dict[str, object] | None = None,
    ) -> CoverageResponse:
        """
        Convenience wrapper returning typed CoverageResponse.
        """
        r = self.try_rubric_coverage(
            assessment_id,
            use_stored_rubric=use_stored_rubric,
            use_stored_question_set=use_stored_question_set,
            rubric=rubric,
            question_set=question_set,
        )
        assert r.status_code == 200, r.text
        return CoverageResponse.model_validate(r.json())

    def rubric_coverage_stored(self, assessment_id: str) -> CoverageResponse:
        """
        Coverage using stored rubric and question set (defaults).
        """
        return self.rubric_coverage(assessment_id)

    def rubric_coverage_inline(
        self,
        assessment_id: str,
        *,
        rubric: dict[str, object],
        question_set: dict[str, object],
    ) -> CoverageResponse:
        """
        Coverage using inline rubric and question set (sets use_stored_* to False).
        """
        return self.rubric_coverage(
            assessment_id,
            use_stored_rubric=False,
            use_stored_question_set=False,
            rubric=rubric,
            question_set=question_set,
        )

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

    def try_run_grading(self, assessment_id: str) -> Response:
        # Start grading
        return self.client.post(
            f"/assessments/{assessment_id}/grading",
            json={},
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
