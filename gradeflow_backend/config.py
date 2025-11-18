import os

from pydantic import BaseModel, Field


class SecurityConfig(BaseModel):
    # JWT
    jwt_algorithm: str = Field(default=os.getenv("JWT_ALGORITHM", "HS256"))
    jwt_access_expires_minutes: int = Field(
        default=int(os.getenv("JWT_ACCESS_EXPIRES_MINUTES", "30"))
    )
    jwt_refresh_expires_days: int = Field(default=int(os.getenv("JWT_REFRESH_EXPIRES_DAYS", "14")))
    jwt_issuer: str = Field(default=os.getenv("JWT_ISSUER", "gradeflow-api"))
    jwt_audience: str = Field(default=os.getenv("JWT_AUDIENCE", "gradeflow-clients"))
    # Symmetric secret for HS256; prefer rotating secrets via key IDs
    jwt_secret: str = Field(
        default=os.getenv("JWT_SECRET", "change-me-in-prod")
    )  # set in environment
    # Optional key ID (kid) for rotation (metadata only for HS256)
    jwt_kid: str | None = Field(default=os.getenv("JWT_KID"))

    # Password policy
    password_min_length: int = Field(default=int(os.getenv("PASSWORD_MIN_LENGTH", "12")))


def get_security_config() -> SecurityConfig:
    return SecurityConfig()
