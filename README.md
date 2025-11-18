# GradeFlow Backend

A FastAPI backend that wraps the GradeFlow Engine to manage assessments, question sets, rubrics, submissions, and grading. It provides JWT-based authentication with access/refresh tokens, membership and roles, and typed request/response models.

This is intended as a thin layer around the GradeFlow Engine.

## Getting Started

### Installation

```bash
pip install -e ".[dev]"
```

### Configuration

Environment variables (sane defaults are provided for local dev):

- JWT_SECRET: symmetric secret for HS256 (default: change-me-in-prod)
- JWT_ALGORITHM: HS256
- JWT_ISSUER: gradeflow-api
- JWT_AUDIENCE: gradeflow-clients
- JWT_ACCESS_EXPIRES_MINUTES: 30
- JWT_REFRESH_EXPIRES_DAYS: 14
- JWT_KID: optional key id
- PASSWORD_MIN_LENGTH: 12

Example local `.env` (optional):
```
JWT_SECRET=test-secret 
JWT_ALGORITHM=HS256 
JWT_ISSUER=gradeflow-api 
JWT_AUDIENCE=gradeflow-clients 
JWT_ACCESS_EXPIRES_MINUTES=30 
JWT_REFRESH_EXPIRES_DAYS=14 
PASSWORD_MIN_LENGTH=12
```

### Run the App

```bash
uvicorn gradeflow_backend.main:app --reload
```
- Docs: http://127.0.0.1:8000/docs
- Health: GET /health -> `{"status": "ok"}`

## Authentication

- Signup: POST /auth/signup (JSON)
- Token (OAuth2 Password): POST /auth/token (form-encoded)
- Refresh: POST /auth/refresh (JSON)
- Logout: POST /auth/logout (requires access token)
- Me: GET /auth/me (requires access token)

Access tokens are used in the Authorization header:
Authorization: Bearer <access_token>


Refresh tokens are single-use (rotation). On refresh, the old refresh token is revoked and a new pair is issued. Logout deletes all stored refresh tokens for the user.

## Roles and Access Control

Membership is tied to assessments with roles:
- viewer: can read assessment data
- editor: can modify question sets, rubrics, submissions, and grading state
- owner: full control, including updating/deleting assessments and managing members

Route guards:
- `member_guard_factory()`: requires membership
- `role_guard_factory("editor" | "owner")`: requires minimum role

## API Overview

- Health
  - GET /health

- Registry (from GradeFlow Engine capabilities)
  - GET /registry/question-set-loaders
  - GET /registry/question-set-savers
  - GET /registry/rubric-loaders
  - GET /registry/submissions-loaders
  - GET /registry/submissions-savers

- Auth
  - POST /auth/signup -> TokenPairResponse
  - POST /auth/token (OAuth2 Password; form fields username=email, password=...) -> TokenPairResponse
  - POST /auth/refresh -> TokenPairResponse
  - POST /auth/logout -> 204
  - GET /auth/me -> MeResponse

- Assessments (requires access token)
  - POST /assessments -> create (creator becomes owner)
  - GET /assessments -> list
  - GET /assessments/{id} -> get (member)
  - PATCH /assessments/{id} -> update (owner)
  - DELETE /assessments/{id} -> delete (owner)

- Memberships (assessment-level)
  - GET /assessments/{id}/members -> list (member)
  - POST /assessments/{id}/members -> add member (owner) [role defaults to viewer]
  - PATCH /assessments/{id}/members/{user_id} -> set role (owner)
  - DELETE /assessments/{id}/members/{user_id} -> remove (owner)

- Question Sets
  - GET /assessments/{id}/question-set -> get (member)
  - PUT /assessments/{id}/question-set -> set by model (editor)
  - PUT /assessments/{id}/question-set/load -> set by data (YAML) (editor)
  - POST /assessments/{id}/question-set/infer -> infer from submissions (editor)
  - POST /assessments/{id}/question-set/parse -> parse submissions (member)
  - DELETE /assessments/{id}/question-set -> delete (editor)

- Rubrics
  - GET /assessments/{id}/rubric -> get (member)
  - PUT /assessments/{id}/rubric -> set by model (editor)
  - PUT /assessments/{id}/rubric/load -> set by data (YAML) (editor)
  - POST /assessments/{id}/rubric/validate -> validate (member)
  - DELETE /assessments/{id}/rubric -> delete (editor)

- Submissions
  - GET /assessments/{id}/submissions -> get (member)
  - PUT /assessments/{id}/submissions -> set by model (editor)
  - PUT /assessments/{id}/submissions/load -> set by data (CSV) (editor)
  - DELETE /assessments/{id}/submissions -> delete (editor)

- Grading
  - GET /assessments/{id}/grading -> get graded results (member)
  - POST /assessments/{id}/grading/run -> run (editor)
  - POST /assessments/{id}/grading/export -> export graded (member)
  - DELETE /assessments/{id}/grading -> delete graded state (editor)

### Response/Request Models

See `gradeflow_backend/schemas/` for Pydantic models. Notable external models from GradeFlow Engine:
- QuestionSet
- Rubric
- RawSubmission, Submission, GradedSubmission
- RuleValidationError

## Example Workflow (cURL)

```bash
# 1) Signup
curl -s -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Super-Strong-Pass-123!"}'

# 2) OAuth2 Password token
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=user@example.com&password=Super-Strong-Pass-123!'

# Export ACCESS and REFRESH from the response
ACCESS="<access_token>"

# 3) Create assessment (auth required)
curl -s -X POST http://localhost:8000/assessments \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"id":"cs1-midterm","name":"Midterm"}'

# 4) Load question set (YAML)
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/question-set/load \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"question_map:\n  q1:\n    type: TEXT\n  q2:\n    type: NUMERIC\n","loader_name":"YAML"}'

# 5) Load rubric (YAML)
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/rubric/load \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"rules:\n  - type: EXACT_MATCH\n    question_id: q1\n    answer: \"Alice\"\n    max_points: 1\n  - type: NUMERIC_RANGE\n    question_id: q2\n    min_value: 0\n    max_value: 100\n    max_points: 2\n","loader_name":"YAML"}'

# 6) Load submissions (CSV)
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/submissions/load \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"student_id,q1,q2\ns1,Alice,90\ns2,Bob,76\n","loader_name":"CSV","loader_kwargs":{}}'

# 7) Run grading
curl -s -X POST http://localhost:8000/assessments/cs1-midterm/grading/run \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{}'

# 8) Export graded (CSV)
curl -s -X POST http://localhost:8000/assessments/cs1-midterm/grading/export \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"saver_name":"CSV"}'
```
## Development

### Formatting and Linting

```bash
ruff format .
ruff check .
```
### Type Checking

```bash
mypy gradeflow_backend
```
### Tests

```bash
pytest --cov=gradeflow_backend --cov-report=term --cov-report=xml
```
Pytest creates a temporary SQLite database per test function via fixtures and overrides the FastAPI dependency injection for sessions.

## License

MIT License.