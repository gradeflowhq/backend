# GradeFlow Backend

A FastAPI backend that wraps the GradeFlow Engine to manage assessments, question sets, rubrics, rules, submissions, and grading. It uses Zitadel as an external identity provider for authentication, with role-based membership and typed request/response models.

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

Settings are loaded from environment variables (or an optional `.env` file) using [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with `env_nested_delimiter='__'`. Nested fields are addressed with `__`, e.g. `ZITADEL__AUTHORITY` sets `settings.zitadel.authority`.

**Zitadel (Identity Provider)** (`ZITADEL__*`)
- `ZITADEL__AUTHORITY` — Zitadel instance URL (default: `https://zitadel.cloud`)
- `ZITADEL__CLIENT_ID` — OAuth2 Client ID from Zitadel (required)
- `ZITADEL__AUDIENCE` — Expected JWT audience (aud) claim; typically the Zitadel Project Resource ID. Falls back to `CLIENT_ID` when empty.
- `ZITADEL__ORG_DOMAIN` — Primary org domain — scopes login so users type username only (optional)
- `ZITADEL__JWKS_CACHE_TTL` — JWKS cache lifetime in seconds (default: `300`). Zitadel rotates keys without notice, so the cache is refreshed periodically and on-demand when an unknown `kid` is encountered.

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
- `EXECUTOR__POLL_INTERVAL_S` — polling interval in seconds for in-memory executors (default: `1.0`)
- `EXECUTOR__NUM_WORKERS` — worker count for in-memory executors (default: `4`)
- `EXECUTOR__CONTAINER_RUNTIME` — `docker` (default) for container executor
- `EXECUTOR__CONTAINER_IMAGE` — engine image (default: `ghcr.io/gradeflowhq/gradeflow-engine:latest`)
- `EXECUTOR__CONTAINER_WORKDIR` — working directory inside the container (default: `/local`)
- `EXECUTOR__CALLBACK_BASE_URL` — absolute base URL for job callbacks (default: `http://host.docker.internal:8000`)
- `EXECUTOR__CALLBACK_TIMEOUT_S` — timeout in seconds for callback POST requests (default: `10`)
- `EXECUTOR__NOMAD_HOST` — Nomad HTTP host (default: `host.docker.internal`)
- `EXECUTOR__NOMAD_PORT` — Nomad HTTP port (default: `4646`)
- `EXECUTOR__NOMAD_TOKEN` — Nomad ACL token (optional)
- `EXECUTOR__NOMAD_NAMESPACE` — Nomad namespace (optional)
- `EXECUTOR__NOMAD_VERIFY_TLS` — verify TLS when talking to Nomad (default: `true`)
- `EXECUTOR__NOMAD_DATACENTERS` — comma-separated list (default: `dc1`)
- `EXECUTOR__NOMAD_CPU` — Nomad task CPU MHz (default: `200`)
- `EXECUTOR__NOMAD_MEMORY_MB` — Nomad task memory MB (default: `512`)

**Grading** (`GRADING__*`)
- `GRADING__MAX_SUBMISSION_PREVIEW` — maximum submissions allowed in a preview run (default: `20`)
- `GRADING__RUN_REQUESTS_PER_MINUTE` — maximum grading-run requests allowed per client per minute (default: `10`)
- `GRADING__PREVIEW_REQUESTS_PER_MINUTE` — maximum grading-preview requests allowed per client per minute (default: `30`)
- `GRADING__COMPLETED_JOB_ESTIMATE_SAMPLE_SIZE` — recent completed jobs used for duration estimates (default: `10`)
- `GRADING__RUBRIC_GRADING_PARALLEL_JOBS` — worker count for rubric grading; `-1` uses all CPUs available to the process, capped by submission count; `0` is invalid (default: `1`)
- `GRADING__RUBRIC_GRADING_PARALLEL_MODE` — rubric grading worker mode: `processes` or `threads` (default: `processes`)

Example `.env` can be found in `.env.example`.

### Database Migrations

The backend uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations. After installation, run:

```bash
alembic upgrade head
```

This applies all pending migrations. When developing locally with SQLite, the app also calls `init_db()` on startup to create tables, but for production databases (PostgreSQL, MySQL/MariaDB) you should always use Alembic.

To generate a new migration after model changes:

```bash
alembic revision --autogenerate -m "description of change"
```

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

Authentication is handled by [Zitadel](https://zitadel.com), an external identity provider. The backend validates Zitadel-issued JWTs (RS256) via JWKS and syncs user info to the local database on first access.

- Me: GET /users/me (requires access token) — returns synced user info from DB

Access tokens are obtained from Zitadel and used in the Authorization header:
```
Authorization: Bearer <access_token>
```

User records are automatically created/updated in the local database when a valid Zitadel token is first seen (email and name synced from token claims or the userinfo endpoint).

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

- Users
  - GET /users/me -> MeResponse (synced from Zitadel token)

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
  - POST /assessments/{id}/question-set/export -> export (member)
  - PUT /assessments/{id}/question-set -> set by model (editor)
  - PUT /assessments/{id}/question-set/upload -> set by raw data (editor)
  - PUT /assessments/{id}/question-set/import -> import via adapter (editor)
  - POST /assessments/{id}/question-set/infer -> infer from submissions (editor)
  - POST /assessments/{id}/question-set/parse -> parse submissions (member)
  - DELETE /assessments/{id}/question-set -> delete (editor)

- Rubrics
  - GET /assessments/{id}/rubric -> get (member)
  - POST /assessments/{id}/rubric/export -> export (member)
  - PUT /assessments/{id}/rubric -> set by model (editor)
  - PUT /assessments/{id}/rubric/upload -> set by raw data (editor)
  - PUT /assessments/{id}/rubric/import -> import via adapter (editor)
  - POST /assessments/{id}/rubric/empty -> initialize an empty rubric (editor)
  - POST /assessments/{id}/rubric/staleness/acknowledge -> acknowledge rubric staleness (editor)
  - POST /assessments/{id}/rubric/validate -> validate (member)
  - POST /assessments/{id}/rubric/sync -> sync rubric to the current question set (editor)
  - GET /assessments/{id}/rubric/overview -> overview and coverage by question (member)
  - DELETE /assessments/{id}/rubric -> delete (editor)

- Rules
  - GET /assessments/{id}/rules -> list stored rules (member)
  - POST /assessments/{id}/rules -> create rule (editor; server assigns ids)
  - GET /assessments/{id}/rules/list?question_id={qid}&path={path} -> compatible rule types for a global, question, or nested context (member)
  - GET /assessments/{id}/rules/schema?type={rule_type}&question_id={qid}&path={path} -> contextual JSON Schema and initial value (member)
  - GET /assessments/{id}/rules/{rule_id} -> get rule (member)
  - PUT /assessments/{id}/rules/{rule_id} -> update rule (editor)
  - DELETE /assessments/{id}/rules/{rule_id} -> delete rule (editor)

- Submissions
  - PUT /assessments/{id}/submissions/source -> upload raw CSV source data (editor)
  - GET /assessments/{id}/submissions/source -> get source data (member)
  - PUT /assessments/{id}/submissions/config -> save import config (editor)
  - GET /assessments/{id}/submissions/config -> get import config (member)
  - GET /assessments/{id}/submissions -> get parsed submissions (member)
  - DELETE /assessments/{id}/submissions -> delete source data and config (editor)

- Grading
  - GET /assessments/{id}/grading -> get graded results (member)
  - GET /assessments/{id}/grading/job -> get current run job (member)
  - DELETE /assessments/{id}/grading/job -> cancel current run job (editor)
  - POST /assessments/{id}/grading -> run grading (editor) -> GradingJob
  - POST /assessments/{id}/grading/adjust -> adjust a single result (editor)
  - POST /assessments/{id}/grading/bulk-adjust -> adjust multiple results (editor)
  - POST /assessments/{id}/grading/download -> download graded output (member)
  - DELETE /assessments/{id}/grading -> delete graded state (editor)
  - POST /assessments/{id}/grading/preview -> run preview (member) -> GradingJob
  - GET /assessments/{id}/grading/preview -> get preview results (member)
  - GET /assessments/{id}/grading/preview/job -> get preview job (member)
  - DELETE /assessments/{id}/grading/preview/job -> cancel preview job (member)

- Jobs
  - GET /jobs/{job_id} -> get job status -> JobStatusResponse
  - POST /jobs/callback/{token} -> executor callback (internal) -> 204

### Staleness Tracking

Each assessment tracks fine-grained `updated_at` timestamps for source data, question set, rubric, and grading results. The `SectionStatus` model (included in question set, rubric, and grading responses) contains an `updated_at` timestamp and an `is_stale` flag. Staleness cascades through the pipeline: if source data is updated after the question set, the question set is marked stale; if the question set is stale or updated after the rubric, the rubric is marked stale; and if the rubric is stale or updated after the grading results, the results are marked stale. This lets the frontend prompt users to re-run downstream steps when upstream data changes.

### Rule Schema Endpoints

Rule endpoints keep the backend thin. The backend loads the assessment question set and submissions, builds an engine `RuleContext`, and delegates compatibility and schema generation to `gradeflow_engine.rules.schema`.

- Omit `question_id` to request global rules.
- Provide `question_id` to request rules for a question.
- Provide `path` to request schemas for nested rule fields or multi-valued value slots.
- Schema responses include JSON Schema and an `initial_value`; they do not include backend-owned UI schemas.
- Clients should use standard JSON Schema fields plus engine-owned `x-gradeflow` metadata.

### Response/Request Models

See `gradeflow_backend/schemas/` for Pydantic models. Notable external models from GradeFlow Engine:
- `QuestionSet`
- `Rubric`
- `RawSubmission`, `Submission`
- `RuleValidationError`
- `SubmissionsSerializerConfig` (discriminated union for CSV / JSON / YAML output)

Key backend schemas:
- `AdjustableQuestionResult` — `QuestionResult` extended with `adjusted_points` / `adjusted_feedback`
- `AdjustableSubmission` — `Submission` with `result_map` typed as `dict[QuestionId, AdjustableQuestionResult]`
- `GradingRunRequest` — `remove_adjustments` (default `false`) to clear manual adjustments on re-grade, and `override_results` (default `true`) to control whether rule results overwrite pre-existing points
- `GradingResponse` — wraps `submissions: list[AdjustableSubmission]` and a `SectionStatus`
- `GradingDownloadRequest` — `serializer: SubmissionsSerializerConfig` to choose output format (CSV / JSON / YAML)
- `GradingDownloadResponse` — `filename`, `data` (bytes), `extension`, and `media_type`
- `GradeAdjustmentRequest` — targets a single `(student_id, question_id)` pair with optional `adjusted_points` / `adjusted_feedback`
- `BulkGradeAdjustmentRequest` — list of `GradeAdjustmentRequest` items (min 1)
- `BulkGradeAdjustmentResponse` — `applied` count, `errors` list, and updated `result`
- `GradingLimitConfig` — `limit`, `selection` (`first` | `random`), and optional `seed` for preview runs
- `GradingPreviewRequest` — optional single `rule` and a `GradingLimitConfig`
- `GradingJob` — returned by run / preview; contains `job_id` and a polling `url`
- `JobStatusResponse` — `job_id`, `status` (`queued` | `running` | `completed` | `failed`), and optional `error`
- `ExportQuestionSetRequest` / `ExportQuestionSetResponse` — serializer config and exported file data
- `ExportRubricRequest` / `ExportRubricResponse` — serializer config and exported file data
- `RulesResponse` — stored rubric rules plus section status
- `RuleTypeOption` / `CompatibleRulesResponse` — compatible rule type, label, and description options for a context
- `RuleSchemaResponse` — contextual rule JSON Schema and initial value
- `RubricOverviewResponse` — rubric coverage and per-question rule overview
- `SourceDataResponse` — parsed `headers`, `rows`, `total_rows`, and `student_id_column` for the uploaded CSV
- `SubmissionsImportConfig` — optional `answer_columns` list and optional `point_columns` mapping (`question_id` -> CSV column name)
- `SectionStatus` — `updated_at` timestamp and `is_stale` flag, included in question set, rubric, and grading responses

## Example Workflow (cURL)

This example assumes you have a Zitadel instance configured and have obtained an access token via the Zitadel OAuth2 flow (Authorization Code or Device Authorization grant).

```bash
# 1) Obtain an access token from your Zitadel instance.
#    Use the Authorization Code flow, Device Authorization flow, or
#    Zitadel's built-in token endpoint with a service user.
#    See: https://zitadel.com/docs/guides/integrate/login
ACCESS="<your_zitadel_access_token>"

# 2) Verify your identity
curl -s http://localhost:8000/users/me \
  -H "Authorization: Bearer $ACCESS"

# 3) Create assessment (auth required; creator becomes owner)
curl -s -X POST http://localhost:8000/assessments \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"name":"Midterm"}'

# Export ASSESSMENT_ID from the response
ASSESSMENT_ID="<id>"

# 4) Upload question set (raw YAML)
curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/question-set/upload \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"question_map:\n  q1:\n    type: TEXT\n  q2:\n    type: NUMERIC\n","serializer":{"format":"yaml"}}'

# 5) Upload rubric (raw YAML)
curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/rubric/upload \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"rules:\n  - type: TEXT_MATCH\n    question_id: q1\n    answers: [\"Alice\"]\n  - type: NUMERIC_RANGE\n    question_id: q2\n    min_value: 0\n    max_value: 100\n","serializer":{"format":"yaml"}}'

# 6a) Upload raw CSV source data
curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/submissions/source \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"student_id,q1,q2\ns1,Alice,90\ns2,Bob,76\n","student_id_column":"student_id"}'

# 6b) (Optional) save import config
curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/submissions/config \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"answer_columns":["q1","q2"]}'

# 7) Run grading
curl -s -X POST http://localhost:8000/assessments/$ASSESSMENT_ID/grading \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{}'

# Export JOB_ID from the response
JOB_ID="<job_id>"

# 8) Poll job status
curl -s http://localhost:8000/jobs/$JOB_ID \
  -H "Authorization: Bearer $ACCESS"

# 9) Get graded results
curl -s http://localhost:8000/assessments/$ASSESSMENT_ID/grading \
  -H "Authorization: Bearer $ACCESS"

# 10) Download graded output (CSV)
curl -s -X POST http://localhost:8000/assessments/$ASSESSMENT_ID/grading/download \
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

Pytest creates a temporary SQLite database per test function via fixtures and overrides the FastAPI dependency injection for sessions. To run against a real database, set `DATABASE__URL` in your environment before running pytest.

## License

MIT License.
