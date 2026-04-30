from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ZitadelSettings(BaseModel):
    authority: str = Field(
        default="https://zitadel.cloud",
        description="Zitadel instance URL (issuer)",
    )
    client_id: str = Field(
        default="",
        description="OAuth2 Client ID from Zitadel",
    )
    audience: str = Field(
        default="",
        description=(
            "Expected JWT audience (aud) claim. In Zitadel this is typically "
            "the Project Resource ID. Falls back to client_id when empty."
        ),
    )
    org_domain: str = Field(
        default="",
        description="Primary org domain — scopes login so users type username only",
    )
    jwks_cache_ttl: int = Field(
        default=300,
        description="JWKS cache lifetime in seconds (Zitadel rotates keys without notice)",
    )


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
    run_requests_per_minute: int = Field(
        default=10,
        ge=1,
        description="Maximum grading-run requests allowed per client per minute.",
    )
    preview_requests_per_minute: int = Field(
        default=30,
        ge=1,
        description="Maximum grading-preview requests allowed per client per minute.",
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    zitadel: ZitadelSettings = ZitadelSettings()
    database: DatabaseSettings = DatabaseSettings()
    cors: CorsSettings = CorsSettings()
    executor: ExecutorSettings = ExecutorSettings()
    grading: GradingSettings = GradingSettings()
    valkey: ValkeySettings = ValkeySettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    # Cached singleton for the entire app
    return AppSettings()
