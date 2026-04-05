from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None


class UpdateMeRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None)
    current_password: str | None = Field(default=None)
    new_password: str | None = Field(default=None, min_length=12, max_length=128)
