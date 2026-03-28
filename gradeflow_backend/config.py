from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseModel):
    # JWT
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_expires_minutes: int = Field(default=30)
    jwt_refresh_expires_days: int = Field(default=14)
    jwt_issuer: str = Field(default="gradeflow-api")
    jwt_audience: str = Field(default="gradeflow-clients")
    jwt_secret: str = Field(default="change-me-in-prod")
    jwt_kid: str | None = Field(default=None)
    # Password policy
    password_min_length: int = Field(default=12)


class DatabaseSettings(BaseModel):
    # Set DB_URL to the SQLAlchemy connection string for your database.
    # SQLite  (default, file-based):  sqlite+pysqlite:///./gradeflow_backend.db
    # SQLite  (in-memory):            sqlite+pysqlite://
    # PostgreSQL (requires [postgresql] extra):  postgresql+psycopg2://user:pass@host:5432/dbname
    # MySQL     (requires [mysql] extra):        mysql+pymysql://user:pass@host:3306/dbname
    # MariaDB   (requires [mysql] extra):        mariadb+pymysql://user:pass@host:3306/dbname
    url: str = Field(default="sqlite+pysqlite:///./gradeflow_backend.db")


class CorsSettings(BaseModel):
    allow_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class ExecutorSettings(BaseModel):
    # Common
    engine_command: str = "gradeflow-engine"

    # INMEMORY_CONTAINER | INMEMORY_SUBPROCESS | SYNCHRONOUS | NOMAD
    executor: Literal["INMEMORY_CONTAINER", "INMEMORY_SUBPROCESS", "SYNCHRONOUS", "NOMAD"] = "NOMAD"
    timeout_s: int = 300

    # In-memory subprocess-specific
    poll_interval_s: float = 1.0
    num_workers: int = 4

    # Container-specific
    container_runtime: str = "docker"
    container_image: str = "ghcr.io/gradeflowhq/gradeflow-engine:latest"
    container_workdir: str = "/local"

    # HTTP callback timeout for job result POSTs
    callback_base_url: str | None = Field(
        default="http://host.docker.internal:8000",
        description="Absolute base URL for job callbacks, e.g. https://api.example.com/ "
        "(if unset, falls back to Request.base_url)",
    )
    callback_timeout_s: int = 10

    # Nomad-specific (host/port instead of full address)
    nomad_host: str | None = Field(
        default="host.docker.internal", description="Nomad HTTP host, e.g. 127.0.0.1"
    )
    nomad_port: int = Field(default=4646, description="Nomad HTTP port, default 4646")
    nomad_token: str | None = Field(default=None, description="Nomad ACL token (optional)")
    nomad_namespace: str | None = Field(default=None, description="Nomad namespace (optional)")
    nomad_verify_tls: bool = Field(default=True, description="Verify TLS when talking to Nomad")
    nomad_datacenters: list[str] = Field(
        default_factory=lambda: ["dc1"],
        description="Nomad datacenters to target for jobs",
    )
    nomad_cpu: int = Field(default=200, description="Nomad task CPU (MHz)")
    nomad_memory_mb: int = Field(default=512, description="Nomad task memory (MB)")


class ValkeySettings(BaseModel):
    url: str = Field(default="valkey://gradeflow-valkey:6379/0")
    preview_ttl_s: int = Field(
        default=300,
        description="TTL (seconds) for preview results stored in Valkey. Defaults to 5 minutes.",
    )


class GradingSettings(BaseModel):
    max_submission_preview: int = Field(
        default=20,
        description="Maximum allowed submissions to preview when no limit is set by the user.",
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    security: SecuritySettings = SecuritySettings()
    database: DatabaseSettings = DatabaseSettings()
    cors: CorsSettings = CorsSettings()
    executor: ExecutorSettings = ExecutorSettings()
    grading: GradingSettings = GradingSettings()
    valkey: ValkeySettings = ValkeySettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    # Cached singleton for the entire app
    return AppSettings()
