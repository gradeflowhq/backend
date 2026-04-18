from pydantic import BaseModel, EmailStr, Field


class ZitadelTokenPayload(BaseModel):
    """
    Typed representation of the JWT claims Zitadel includes in access tokens.
    Only the fields we actually use are declared — extra fields are ignored.
    """

    sub: str = Field(..., description="Zitadel user ID")
    email: str | None = Field(default=None)
    name: str | None = Field(default=None)
    iss: str = Field(..., description="Token issuer")
    aud: str | list[str] = Field(..., description="Token audience")


class MeResponse(BaseModel):
    """Response for the /users/me endpoint — sourced from the local DB user."""

    id: str
    email: EmailStr
    name: str | None = None
