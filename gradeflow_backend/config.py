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
    # Example: sqlite+pysqlite:///./gradeflow_backend.db
    url: str = Field(default="sqlite+pysqlite:///./gradeflow_backend.db", alias="DB_URL")


class CorsSettings(BaseModel):
    allow_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class ExecutorSettings(BaseModel):
    # Common
    engine_command: str = "gradeflow-engine"

    # INMEMORY_CONTAINER | INMEMORY_SUBPROCESS | SYNCHRONOUS
    job_executor: Literal["INMEMORY_CONTAINER", "INMEMORY_SUBPROCESS", "SYNCHRONOUS"] = (
        "INMEMORY_SUBPROCESS"
    )
    job_timeout_s: int = 300
    job_poll_interval_s: float = 1.0
    job_num_workers: int = 4

    # Container-specific
    job_container_runtime: str = "docker"
    job_container_image: str = "gradeflow-engine:latest"
    job_container_workdir: str = "/workspace"

    # HTTP callback timeout for job result POSTs
    callback_timeout_s: int = 10


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",  # allow plain env names (e.g., JWT_SECRET)
        env_file=".env",  # optional; used if present
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,  # allow aliases like DB_URL
    )

    security: SecuritySettings = SecuritySettings()
    database: DatabaseSettings = DatabaseSettings()
    cors: CorsSettings = CorsSettings()
    executor: ExecutorSettings = ExecutorSettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    # Cached singleton for the entire app
    return AppSettings()
