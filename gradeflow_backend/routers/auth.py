from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.auth import get_current_user_id
from gradeflow_backend.repositories.tokens import RefreshTokenRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenPairResponse,
)
from gradeflow_backend.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_service(db: Session = Depends(get_session)) -> AuthService:
    users = UserRepository(db)
    tokens = RefreshTokenRepository(db)
    return AuthService(users, tokens)


@router.post("/signup", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, svc: AuthService = Depends(get_service)) -> TokenPairResponse:
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
    svc: AuthService = Depends(get_service),
) -> TokenPairResponse:
    # OAuth2PasswordRequestForm uses 'username' for the principal; we use email as the principal
    req = LoginRequest(email=form.username, password=form.password)
    return svc.login(req)


@router.post("/refresh", response_model=TokenPairResponse, status_code=status.HTTP_200_OK)
def refresh(req: RefreshRequest, svc: AuthService = Depends(get_service)) -> TokenPairResponse:
    return svc.refresh(req)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user_id: str = Depends(get_current_user_id),
    svc: AuthService = Depends(get_service),
) -> None:
    svc.logout(current_user_id)


@router.get("/me", response_model=MeResponse)
def me(
    current_user_id: str = Depends(get_current_user_id),
    svc: AuthService = Depends(get_service),
) -> MeResponse:
    return svc.me(current_user_id)
