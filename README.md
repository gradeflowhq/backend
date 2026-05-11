# GradeFlow Backend

GradeFlow Backend is a FastAPI service for managing assessments around the
GradeFlow Engine. It owns authentication, membership, persistence, source CSV
state, async grading jobs, manual adjustments, and API-friendly wrappers around
engine models. The engine remains the source of truth for question models,
rubric rules, adapters, serializers, validation, inference, and grading.

## What It Does

- Authenticates Zitadel-issued JWTs and syncs users into the local database.
- Stores assessments, metadata, members, source CSV data, import config,
  question sets, rubrics, grading jobs, and grading results.
- Imports, exports, infers, syncs, and edits GradeFlow Engine `QuestionSet`
  objects.
- Imports, exports, validates, repairs, and edits GradeFlow Engine `Rubric`
  objects and individual rules.
- Runs grading and preview jobs through a pluggable executor.
- Tracks staleness across source data, question sets, rubrics, and results.
- Caches preview results in Valkey and persists full grading results in SQL.

## Installation

```bash
pip install -e ".[dev]"
```

Install the database driver that matches `DATABASE__URL`:

```bash
pip install -e ".[postgresql]"
pip install -e ".[mysql]"
```

The MySQL extra also covers MariaDB.

## Configuration

Settings are loaded with `pydantic-settings` from environment variables or a
local `.env` file. Nested settings use `__`, so `ZITADEL__AUTHORITY` sets
`settings.zitadel.authority`.

Example values live in `.env.example`.

### Zitadel

`ZITADEL__CLIENT_ID` is required at startup.

| Variable | Default | Notes |
|---|---:|---|
| `ZITADEL__AUTHORITY` | `https://zitadel.cloud` | Issuer URL. Set this to your actual Zitadel instance in production. |
| `ZITADEL__CLIENT_ID` | empty | OAuth2 client ID. Also used as the default expected audience. |
| `ZITADEL__AUDIENCE` | empty | Expected JWT `aud`; commonly a Zitadel Project Resource ID. |
| `ZITADEL__ORG_DOMAIN` | empty | Adds `org_domain` to the authorization URL. |
| `ZITADEL__JWKS_CACHE_TTL` | `300` | JWKS cache TTL in seconds. |

### Database

Set `DATABASE__URL` to a SQLAlchemy URL:

```text
sqlite+pysqlite:///./gradeflow_backend.db
sqlite+pysqlite://
postgresql+psycopg2://user:pass@host:5432/dbname
mysql+pymysql://user:pass@host:3306/dbname
mariadb+pymysql://user:pass@host:3306/dbname
```

SQLite is useful for local development. Use Alembic migrations for shared or
production databases.

### CORS

| Variable | Default |
|---|---|
| `CORS__ALLOW_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` |
| `CORS__ALLOW_CREDENTIALS` | `true` |
| `CORS__ALLOW_METHODS` | `["*"]` |
| `CORS__ALLOW_HEADERS` | `["*"]` |

### Valkey

| Variable | Default | Notes |
|---|---:|---|
| `VALKEY__URL` | `valkey://gradeflow-valkey:6379/0` | Used for preview result cache and rate limiting. |
| `VALKEY__PREVIEW_TTL_S` | `300` | Preview cache TTL in seconds. |

### Executor

`EXECUTOR__EXECUTOR` selects the job backend:

- `NOMAD` (default)
- `INMEMORY_CONTAINER`
- `INMEMORY_SUBPROCESS`
- `SYNCHRONOUS`

Common settings:

| Variable | Default |
|---|---:|
| `EXECUTOR__ENGINE_COMMAND` | `gradeflow-engine` |
| `EXECUTOR__TIMEOUT_S` | `300` |
| `EXECUTOR__POLL_INTERVAL_S` | `1.0` |
| `EXECUTOR__NUM_WORKERS` | `4` |
| `EXECUTOR__CALLBACK_BASE_URL` | `http://host.docker.internal:8000` |
| `EXECUTOR__CALLBACK_TIMEOUT_S` | `10` |

Container settings:

| Variable | Default |
|---|---:|
| `EXECUTOR__CONTAINER_RUNTIME` | `docker` |
| `EXECUTOR__CONTAINER_IMAGE` | `ghcr.io/gradeflowhq/gradeflow-engine:latest` |
| `EXECUTOR__CONTAINER_WORKDIR` | `/local` |

Nomad settings:

| Variable | Default |
|---|---:|
| `EXECUTOR__NOMAD_HOST` | `host.docker.internal` |
| `EXECUTOR__NOMAD_PORT` | `4646` |
| `EXECUTOR__NOMAD_TOKEN` | empty |
| `EXECUTOR__NOMAD_NAMESPACE` | empty |
| `EXECUTOR__NOMAD_VERIFY_TLS` | `true` |
| `EXECUTOR__NOMAD_DATACENTERS` | `["dc1"]` |
| `EXECUTOR__NOMAD_CPU` | `200` |
| `EXECUTOR__NOMAD_MEMORY_MB` | `512` |

External executors receive a signed one-time callback URL. The callback endpoint
validates both the token and `X-GradeFlow-Signature`.

### Grading

| Variable | Default | Notes |
|---|---:|---|
| `GRADING__MAX_SUBMISSION_PREVIEW` | `20` | Upper bound for preview limits. |
| `GRADING__RUN_REQUESTS_PER_MINUTE` | `10` | Per-client rate limit. |
| `GRADING__PREVIEW_REQUESTS_PER_MINUTE` | `30` | Per-client rate limit. |
| `GRADING__COMPLETED_JOB_ESTIMATE_SAMPLE_SIZE` | `10` | Recent completed jobs used for estimates. |
| `GRADING__COMPLETED_JOB_ESTIMATE_EWMA_ALPHA` | `0.5` | EWMA smoothing factor for estimates. |
| `GRADING__RUBRIC_GRADING_PARALLEL_JOBS` | `1` | Use `-1` for all available CPUs; `0` is invalid. |
| `GRADING__RUBRIC_GRADING_PARALLEL_MODE` | `processes` | `processes` or `threads`. |

## Database Migrations

Run migrations before serving a shared database:

```bash
alembic upgrade head
```

Create a migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

The app also calls `init_db()` on startup, which is convenient for local SQLite
development. Production deployments should still rely on Alembic. The Docker
entrypoint runs `alembic upgrade head` before starting Uvicorn.

## Running Locally

```bash
uvicorn gradeflow_backend.main:app --reload
```

- OpenAPI docs: http://127.0.0.1:8000/docs
- Health check: `GET /health` returns `{"status": "ok"}`

## Running With Containers

```bash
docker network create gradeflow

docker run --name gradeflow-valkey --network gradeflow \
  -d valkey/valkey

docker run --name gradeflow-mariadb --network gradeflow \
  --env MARIADB_USER=mariadb \
  --env MARIADB_PASSWORD=my-secret-pw \
  --env MARIADB_DATABASE=gradeflow \
  --env MARIADB_ROOT_PASSWORD=my-secret-pw \
  -d mariadb:latest

docker run --name gradeflow-backend --network gradeflow \
  --env-file .env \
  -p 8000:8000 \
  -d ghcr.io/gradeflowhq/gradeflow-backend:latest
```

For Nomad or container executors, make sure `EXECUTOR__CALLBACK_BASE_URL` is an
absolute URL that the grading runtime can reach.

## Authentication And Roles

The backend validates Zitadel access tokens locally with RS256 and JWKS. On first
authenticated access it creates or links a local user record using the Zitadel
subject, email, and name. If the token does not include email/name claims, the
backend calls Zitadel's userinfo endpoint.

Use bearer tokens:

```http
Authorization: Bearer <access_token>
```

Assessment membership is role based:

| Role | Access |
|---|---|
| `viewer` | Read assessment data and run grading previews. |
| `editor` | Modify source data, question sets, rubrics, rules, and grading state. |
| `owner` | Full control, including assessment updates/deletes and member management. |

## Engine Integration

The backend delegates core grading semantics to GradeFlow Engine:

- Question types: `TEXT`, `NUMERIC`, `CHOICE`, `MULTI_VALUED`.
- Built-in raw submission adapter: `csv`.
- Built-in question set and rubric adapter: `examplify`.
- Built-in question set/rubric serializer: `yaml`.
- Built-in graded submission serializers: `csv`, `json`, `yaml`.
- Rule families include text, numeric, choice, composite, multi-valued, custom
  code, code tests, conditional, assumption set, and bonus rules.

Rule schema endpoints build an engine `RuleContext` and return contextual JSON
Schema plus `initial_value`. Schemas may include engine metadata under
`x-gradeflow`, such as `input` hints (`code`, `string-list`, `rule`,
`rule-list`) and answer suggestions derived from stored submissions.

## Staleness And Status

Assessments track these timestamps independently:

- `source_updated_at`
- `question_set_updated_at`
- `rubric_updated_at`
- `results_updated_at`

Responses for question sets, rubrics, and grading include a `SectionStatus`
with `updated_at` and `is_stale`. Staleness cascades downstream:

- Source changes make the question set stale.
- A stale or newer question set makes the rubric stale.
- A stale or newer rubric makes grading results stale.

Question-set status also reports drift against current source data: missing
question IDs, extra question IDs, and newly observed choice options. Question-set
sync can add missing questions, remove extra questions, and expand choice
options from submissions. Rubric overview reports coverage, validation errors,
and stale rule references; rubric sync removes rules that reference deleted
questions, while repair reloads the stored rubric non-strictly and drops invalid
rules.

## API Overview

### Health And Registry

- `GET /health`
- `GET /registry/adapters/raw-submissions`
- `GET /registry/adapters/question-sets`
- `GET /registry/adapters/rubrics`
- `GET /registry/serializers/question-sets`
- `GET /registry/serializers/rubrics`
- `GET /registry/serializers/submissions`

### Users

- `GET /users/me` - current synced user.

### Assessments

- `POST /assessments` - create assessment; creator becomes owner.
- `GET /assessments` - list assessments visible to current user, with summary.
- `GET /assessments/{id}` - get assessment.
- `PATCH /assessments/{id}` - update name/description.
- `DELETE /assessments/{id}` - delete assessment.
- `GET /assessments/{id}/metadata`
- `PUT /assessments/{id}/metadata`
- `GET /assessments/{id}/metadata/{key}`
- `PUT /assessments/{id}/metadata/{key}`
- `DELETE /assessments/{id}/metadata/{key}`

### Memberships

- `GET /assessments/{id}/members`
- `POST /assessments/{id}/members` - add by email; role defaults to viewer.
- `PATCH /assessments/{id}/members/{user_id}`
- `DELETE /assessments/{id}/members/{user_id}`

### Submissions

- `PUT /assessments/{id}/submissions/source` - upload CSV source data.
- `GET /assessments/{id}/submissions/source` - preview stored CSV rows.
- `PUT /assessments/{id}/submissions/config` - set `answer_columns` and `point_columns`.
- `GET /assessments/{id}/submissions/config`
- `GET /assessments/{id}/submissions` - derive raw submissions from source/config.
- `DELETE /assessments/{id}/submissions`

### Question Sets

- `GET /assessments/{id}/question-set`
- `GET /assessments/{id}/question-set/status` - status plus drift.
- `POST /assessments/{id}/question-set/sync`
- `POST /assessments/{id}/question-set/staleness/acknowledge`
- `POST /assessments/{id}/question-set/export`
- `PUT /assessments/{id}/question-set` - set by model.
- `PUT /assessments/{id}/question-set/upload` - load serialized data.
- `PUT /assessments/{id}/question-set/import` - load through an adapter.
- `POST /assessments/{id}/question-set/infer`
- `POST /assessments/{id}/question-set/parse`
- `DELETE /assessments/{id}/question-set`
- `POST /assessments/{id}/question-set/questions`
- `GET /assessments/{id}/question-set/questions/{question_id}`
- `PUT /assessments/{id}/question-set/questions/{question_id}`
- `DELETE /assessments/{id}/question-set/questions/{question_id}`

### Rubrics And Rules

- `GET /assessments/{id}/rubric`
- `POST /assessments/{id}/rubric/export`
- `PUT /assessments/{id}/rubric`
- `PUT /assessments/{id}/rubric/upload`
- `PUT /assessments/{id}/rubric/import`
- `POST /assessments/{id}/rubric/empty`
- `POST /assessments/{id}/rubric/staleness/acknowledge`
- `POST /assessments/{id}/rubric/validate`
- `POST /assessments/{id}/rubric/sync`
- `POST /assessments/{id}/rubric/repair`
- `GET /assessments/{id}/rubric/overview`
- `DELETE /assessments/{id}/rubric`
- `GET /assessments/{id}/rules`
- `POST /assessments/{id}/rules`
- `GET /assessments/{id}/rules/list?question_id={qid}&path={path}`
- `GET /assessments/{id}/rules/schema?type={rule_type}&question_id={qid}&path={path}`
- `GET /assessments/{id}/rules/{rule_id}`
- `PUT /assessments/{id}/rules/{rule_id}`
- `DELETE /assessments/{id}/rules/{rule_id}`

### Grading And Jobs

- `GET /assessments/{id}/grading`
- `POST /assessments/{id}/grading` - submit full grading run.
- `GET /assessments/{id}/grading/job`
- `DELETE /assessments/{id}/grading/job`
- `POST /assessments/{id}/grading/adjust`
- `POST /assessments/{id}/grading/bulk-adjust`
- `POST /assessments/{id}/grading/download`
- `DELETE /assessments/{id}/grading`
- `POST /assessments/{id}/grading/preview` - submit preview job.
- `GET /assessments/{id}/grading/preview` - read and clear cached preview result.
- `GET /assessments/{id}/grading/preview/job`
- `DELETE /assessments/{id}/grading/preview/job`
- `GET /jobs/{job_id}`
- `POST /jobs/callback/{token}` - internal signed executor callback.

Preview requests accept an optional single `rule` and a `config`:

```json
{
  "rule": null,
  "config": {
    "limit": 5,
    "selection": "random_unique",
    "seed": 123
  }
}
```

`selection` can be `first`, `random`, or `random_unique`. Preview jobs do not
persist grading results; they store a short-lived Valkey result that is consumed
by `GET /grading/preview`.

## Error Format

Errors use a consistent JSON shape:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "errors": ["Question id is required."]
}
```

Backend `AppError`s, FastAPI/Starlette HTTP errors, request validation errors,
Pydantic validation errors, and GradeFlow Engine errors are all normalized into
this contract.

## Example Workflow

This example assumes you already have a Zitadel access token.

```bash
ACCESS="<your_zitadel_access_token>"

curl -s -X POST http://localhost:8000/assessments \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"name":"Midterm","description":"Spring exam"}'

ASSESSMENT_ID="<id-from-response>"

curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/submissions/source \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"data":"student_id,q1,q2\ns1,Alice,90\ns2,Bob,76\n","student_id_column":"student_id"}'

curl -s -X POST http://localhost:8000/assessments/$ASSESSMENT_ID/question-set/infer \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"commit":true}'

curl -s -X PUT http://localhost:8000/assessments/$ASSESSMENT_ID/rubric/upload \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"serializer":{"format":"yaml"},"data":"rules:\n  - type: MULTIPLE_CHOICE\n    question_id: q1\n    answer: [\"alice\"]\n    mode: ALL\n  - type: NUMERIC_RANGE\n    question_id: q2\n    min_value: 0\n    max_value: 100\n"}'

curl -s -X POST http://localhost:8000/assessments/$ASSESSMENT_ID/grading \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"remove_adjustments":false,"override_results":true}'

JOB_ID="<job-id-from-response>"

curl -s http://localhost:8000/jobs/$JOB_ID \
  -H "Authorization: Bearer $ACCESS"

curl -s http://localhost:8000/assessments/$ASSESSMENT_ID/grading \
  -H "Authorization: Bearer $ACCESS"

curl -s -X POST http://localhost:8000/assessments/$ASSESSMENT_ID/grading/download \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"serializer":{"format":"csv"}}'
```

## Development

```bash
ruff format .
ruff check .
mypy gradeflow_backend
pytest --cov=gradeflow_backend --cov-report=term --cov-report=xml
```

Tests use a per-test SQLite database by default and fake Valkey. Set `DB_URL`
to run the test fixtures against a different database.

## License

MIT License.
