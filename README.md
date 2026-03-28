# GradeFlow Backend

A FastAPI backend that wraps the GradeFlow Engine to manage assessments, question sets, rubrics, submissions, and grading. It provides JWT-based authentication with access/refresh tokens, membership and roles, and typed request/response models.

This is intended as a thin layer around the GradeFlow Engine.

## Getting Started

### Installation

```bash
pip install -e ".[dev]"
```

For PostgreSQL support:
```bash
pip install -e ".[postgresql]"
```

For MySQL / MariaDB support:
```bash
pip install -e ".[mysql]"
```

### Configuration

Settings are loaded from environment variables (or an optional `.env` file) using [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with `env_nested_delimiter='__'`. Nested fields are addressed with `__`, e.g. `SECURITY__JWT_SECRET` sets `settings.security.jwt_secret`.

**Security** (`SECURITY__*`)
- `SECURITY__JWT_SECRET` — symmetric secret for HS256 (default: `change-me-in-prod`)
- `SECURITY__JWT_ALGORITHM` — default: `HS256`
- `SECURITY__JWT_ISSUER` — default: `gradeflow-api`
- `SECURITY__JWT_AUDIENCE` — default: `gradeflow-clients`
- `SECURITY__JWT_ACCESS_EXPIRES_MINUTES` — default: `30`
- `SECURITY__JWT_REFRESH_EXPIRES_DAYS` — default: `14`
- `SECURITY__JWT_KID` — optional key id
- `SECURITY__PASSWORD_MIN_LENGTH` — default: `12`

**Database** (`DATABASE__*`)

Set `DATABASE__URL` to the SQLAlchemy connection string for your database:
- SQLite file (default): `sqlite+pysqlite:///./gradeflow_backend.db`
- SQLite in-memory: `sqlite+pysqlite://`
- PostgreSQL (requires `[postgresql]` extra): `postgresql+psycopg2://user:pass@host:5432/dbname`
- MySQL (requires `[mysql]` extra): `mysql+pymysql://user:pass@host:3306/dbname`
- MariaDB (requires `[mysql]` extra): `mariadb+pymysql://user:pass@host:3306/dbname`

**Valkey (preview cache)** (`VALKEY__*`)
- `VALKEY__URL` — default: `valkey://gradeflow-valkey:6379/0`
- `VALKEY__PREVIEW_TTL_S` — TTL in seconds for cached preview results (default: `300`)

**Executor** (`EXECUTOR__*`)
- `EXECUTOR__EXECUTOR` — `NOMAD` (default) | `INMEMORY_CONTAINER` | `INMEMORY_SUBPROCESS` | `SYNCHRONOUS`
- `EXECUTOR__ENGINE_COMMAND` — gradeflow-engine command (default: `gradeflow-engine`)
- `EXECUTOR__TIMEOUT_S` — job timeout in seconds (default: `300`)
- `EXECUTOR__NUM_WORKERS` — worker count for in-memory executors (default: `4`)
- `EXECUTOR__CONTAINER_RUNTIME` — `docker` (default) for container executor
- `EXECUTOR__CONTAINER_IMAGE` — engine image (default: `ghcr.io/gradeflowhq/gradeflow-engine:latest`)
- `EXECUTOR__CALLBACK_BASE_URL` — absolute base URL for job callbacks (default: `http://host.docker.internal:8000`)
- `EXECUTOR__NOMAD_HOST` — Nomad HTTP host (default: `host.docker.internal`)
- `EXECUTOR__NOMAD_PORT` — Nomad HTTP port (default: `4646`)
- `EXECUTOR__NOMAD_TOKEN` — Nomad ACL token (optional)
- `EXECUTOR__NOMAD_NAMESPACE` — Nomad namespace (optional)
- `EXECUTOR__NOMAD_DATACENTERS` — comma-separated list (default: `dc1`)
- `EXECUTOR__NOMAD_CPU` — Nomad task CPU MHz (default: `200`)
- `EXECUTOR__NOMAD_MEMORY_MB` — Nomad task memory MB (default: `512`)

**Grading** (`GRADING__*`)
- `GRADING__MAX_SUBMISSION_PREVIEW` — maximum submissions allowed in a preview run (default: `20`)

Example `.env` can be found in `.env.example`.

### Run the App

```bash
uvicorn gradeflow_backend.main:app --reload
```
- Docs: http://127.0.0.1:8000/docs
- Health: GET /health -> `{"status": "ok"}`

### Using Containers

Setup network
```
docker network create gradeflow
```

Run Valkey
```
docker run --name gradeflow-valkey --network gradeflow -d valkey/valkey
```

Run MariaDB
```
docker run --name gradeflow-mariadb --network gradeflow --env MARIADB_USER=mariadb --env MARIADB_PASSWORD=my-secret-pw --env MARIADB_DATABASE=gradeflow --env MARIADB_ROOT_PASSWORD=my-secret-pw -d mariadb:latest
```

Run backend
```
docker run --name gradeflow-backend --network gradeflow --env-file .env -p 8000:8000 -d ghcr.io/gradeflowhq/gradeflow-backend:latest
```

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

- Registry (GradeFlow Engine capabilities)
  - GET /registry/adapters/raw-submissions
  - GET /registry/adapters/question-sets
  - GET /registry/adapters/rubrics
  - GET /registry/serializers/question-sets
  - GET /registry/serializers/rubrics
  - GET /registry/serializers/submissions

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
  - PUT /assessments/{id}/question-set/upload -> set by raw data (editor)
  - PUT /assessments/{id}/question-set/import -> import via adapter (editor)
  - POST /assessments/{id}/question-set/infer -> infer from submissions (editor)
  - POST /assessments/{id}/question-set/parse -> parse submissions (member)
  - DELETE /assessments/{id}/question-set -> delete (editor)

- Rubrics
  - GET /assessments/{id}/rubric -> get (member)
  - PUT /assessments/{id}/rubric -> set by model (editor)
  - PUT /assessments/{id}/rubric/upload -> set by raw data (editor)
  - PUT /assessments/{id}/rubric/import -> import via adapter (editor)
  - POST /assessments/{id}/rubric/validate -> validate (member)
  - POST /assessments/{id}/rubric/coverage -> coverage report (member)
  - DELETE /assessments/{id}/rubric -> delete (editor)

- Submissions
  - PUT /assessments/{id}/submissions/source -> upload raw CSV source data (editor)
  - GET /assessments/{id}/submissions/source -> get source data (member)
  - PUT /assessments/{id}/submissions/config -> save import config (editor)
  - GET /assessments/{id}/submissions/config -> get import config (member)
  - GET /assessments/{id}/submissions -> get parsed submissions (member)
  - PUT /assessments/{id}/submissions/import -> import using stored source + config (editor)
  - DELETE /assessments/{id}/submissions -> delete (editor)

- Grading
  - GET /assessments/{id}/grading -> get graded results (member)
  - GET /assessments/{id}/grading/job -> get current run job status (member)
  - POST /assessments/{id}/grading -> run grading (editor) -> GradingJob
  - POST /assessments/{id}/grading/adjust -> adjust a single result (editor)
  - POST /assessments/{id}/grading/download -> download graded output (member)
  - DELETE /assessments/{id}/grading -> delete graded state (editor)
  - POST /assessments/{id}/grading/preview -> run preview (member) -> GradingJob
  - GET /assessments/{id}/grading/preview -> get preview results (member)
  - GET /assessments/{id}/grading/preview/job -> get preview job status (member)

### Response/Request Models

See `gradeflow_backend/schemas/` for Pydantic models. Notable external models from GradeFlow Engine:
- `QuestionSet`
- `Rubric`
- `RawSubmission`, `Submission`
- `RuleValidationError`
- `SubmissionsSerializerConfig` (discriminated union for CSV / JSON / YAML output)

Key backend schemas:
- `AdjustableSubmission` — `Submission` extended with per-question `adjusted_points` / `adjusted_feedback`
- `GradingResponse` — wraps `submissions: list[AdjustableSubmission]`
- `GradeAdjustmentRequest` — targets a single `(student_id, question_id)` pair
- `GradingJob` — returned by run / preview; contains `job_id` and a polling `url`
- `SourceDataResponse` — parsed headers, rows, and `student_id_column` for the uploaded CSV
- `SubmissionsImportConfig` — `answer_columns` and optional `point_columns` mapping

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

# Export ACCESS from the response
ACCESS="<access_token>"

# 3) Create assessment (auth required)
curl -s -X POST http://localhost:8000/assessments \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"id":"cs1-midterm","name":"Midterm"}'

# 4) Upload question set (raw YAML)
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/question-set/upload \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"question_map:\n  q1:\n    type: TEXT\n  q2:\n    type: NUMERIC\n","adapter_name":"YAML"}'

# 5) Upload rubric (raw YAML)
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/rubric/upload \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"rules:\n  - type: EXACT_MATCH\n    question_id: q1\n    answer: \"Alice\"\n    max_points: 1\n  - type: NUMERIC_RANGE\n    question_id: q2\n    min_value: 0\n    max_value: 100\n    max_points: 2\n","adapter_name":"YAML"}'

# 6a) Upload raw CSV source data
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/submissions/source \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"student_id,q1,q2\ns1,Alice,90\ns2,Bob,76\n","student_id_column":"student_id"}'

# 6b) (Optional) save import config
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/submissions/config \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"answer_columns":["q1","q2"]}'

# 6c) Import submissions from stored source + config
curl -s -X PUT http://localhost:8000/assessments/cs1-midterm/submissions/import \
  -H "Authorization: Bearer $ACCESS"

# 7) Run grading
curl -s -X POST http://localhost:8000/assessments/cs1-midterm/grading \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{}'

# 8) Download graded output (CSV)
curl -s -X POST http://localhost:8000/assessments/cs1-midterm/grading/download \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"serializer":{"format":"csv"}}'
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

Pytest creates a temporary SQLite database per test function via fixtures and overrides the FastAPI dependency injection for sessions. To run against a real database, set `DB_URL` in your environment before running pytest.

## License

MIT License.