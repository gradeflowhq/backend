from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from gradeflow_backend.dependencies.auth import get_current_user_id
from gradeflow_backend.dependencies.services import get_auth_service
from gradeflow_backend.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenPairResponse,
    UpdateMeRequest,
)
from gradeflow_backend.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def signup(
    req: SignupRequest,
    svc: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    return svc.signup(req)


@router.post(
    "/token",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtain access/refresh tokens",
    description="OAuth2 Password flow. Use your email as the username.",
)
def issue_token(
    form: OAuth2PasswordRequestForm = Depends(),
    svc: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    # OAuth2PasswordRequestForm uses 'username' for the principal; we use email
    return svc.login(LoginRequest(email=form.username, password=form.password))


@router.post("/refresh", response_model=TokenPairResponse, status_code=status.HTTP_200_OK)
def refresh(
    req: RefreshRequest,
    svc: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    return svc.refresh(req)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user_id: str = Depends(get_current_user_id),
    svc: AuthService = Depends(get_auth_service),
) -> None:
    svc.logout(current_user_id)


@router.get("/me", response_model=MeResponse)
def me(
    current_user_id: str = Depends(get_current_user_id),
    svc: AuthService = Depends(get_auth_service),
) -> MeResponse:
    return svc.me(current_user_id)


@router.patch(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description=(
        "Update name, email, and/or password for the authenticated user. "
        "Changing email or password requires current_password to be supplied."
    ),
)
def update_me(
    req: UpdateMeRequest,
    current_user_id: str = Depends(get_current_user_id),
    svc: AuthService = Depends(get_auth_service),
) -> MeResponse:
    return svc.update_me(current_user_id, req)
