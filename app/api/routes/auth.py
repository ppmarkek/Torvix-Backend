from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.db.session import get_session
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.user import (
    EmailExists,
    EmailExistsResponse,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SessionDep = Annotated[Session, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _utcnow_naive() -> datetime:
    return datetime.utcnow()


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _refresh_expires_at() -> datetime:
    return _utcnow_naive() + timedelta(days=int(settings.REFRESH_TOKEN_DAYS))


def _is_session_active(auth_session: AuthSession) -> bool:
    if auth_session.revoked_at is not None:
        return False
    return _to_utc_naive(auth_session.expires_at) > _utcnow_naive()


def _issue_tokens_for_user(session: Session, user_id: int) -> TokenResponse:
    auth_session = AuthSession(
        user_id=user_id,
        refresh_token_hash="",
        expires_at=_refresh_expires_at(),
    )
    session.add(auth_session)
    session.flush()
    if auth_session.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session creation failed",
        )

    refresh_token = create_refresh_token(user_id, session_id=auth_session.id)
    auth_session.refresh_token_hash = hash_refresh_token(refresh_token)
    access_token = create_access_token(user_id, extra_claims={"sid": auth_session.id})
    session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _get_user_by_email(session: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    statement = select(User).where(func.lower(User.email) == normalized_email)
    return session.exec(statement).first()


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    unauthorized = _unauthorized()
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized

    user = session.get(User, user_id)
    auth_session = session.get(AuthSession, session_id)
    if user is None or auth_session is None:
        raise unauthorized
    if auth_session.user_id != user_id or not _is_session_active(auth_session):
        raise unauthorized

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/email_exists", response_model=EmailExistsResponse)
def email_exists(payload: Annotated[EmailExists, Depends()], session: SessionDep) -> EmailExistsResponse:
    existing_user = _get_user_by_email(session, payload.email)
    normalized_email = payload.email.strip().lower()
    return EmailExistsResponse(email=normalized_email, exists=existing_user is not None)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, session: SessionDep) -> User:
    existing_user = _get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = User(
        email=payload.email.strip().lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        birth_date=payload.birth_date,
        weight=payload.weight,
        weight_metric=payload.weight_metric,
        height=payload.height,
        height_metric=payload.height_metric,
        what_do_you_want_to_achieve=payload.what_do_you_want_to_achieve,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, session: SessionDep) -> TokenResponse:
    user = _get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise _unauthorized("Incorrect email or password")

    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User record is invalid",
        )

    return _issue_tokens_for_user(session, user.id)


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, session: SessionDep) -> TokenResponse:
    unauthorized = _unauthorized("Invalid refresh token")
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
        user_id = int(token_payload["sub"])
        session_id = int(token_payload["sid"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized

    auth_session = session.get(AuthSession, session_id)
    if auth_session is None or auth_session.user_id != user_id:
        raise unauthorized
    if not _is_session_active(auth_session):
        raise unauthorized
    if not verify_refresh_token(payload.refresh_token, auth_session.refresh_token_hash):
        raise unauthorized

    user = session.get(User, user_id)
    if user is None:
        raise unauthorized

    auth_session.revoked_at = _utcnow_naive()
    new_auth_session = AuthSession(
        user_id=user_id,
        refresh_token_hash="",
        expires_at=_refresh_expires_at(),
    )
    session.add(new_auth_session)
    session.flush()
    if new_auth_session.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session rotation failed",
        )

    refresh_token = create_refresh_token(user_id, session_id=new_auth_session.id)
    new_auth_session.refresh_token_hash = hash_refresh_token(refresh_token)
    access_token = create_access_token(user_id, extra_claims={"sid": new_auth_session.id})
    session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=LogoutResponse)
def logout(payload: RefreshTokenRequest, session: SessionDep) -> LogoutResponse:
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
        user_id = int(token_payload["sub"])
        session_id = int(token_payload["sid"])
    except (KeyError, TypeError, ValueError):
        return LogoutResponse()

    auth_session = session.get(AuthSession, session_id)
    if auth_session is None or auth_session.user_id != user_id:
        return LogoutResponse()
    if not verify_refresh_token(payload.refresh_token, auth_session.refresh_token_hash):
        return LogoutResponse()

    if auth_session.revoked_at is None:
        auth_session.revoked_at = _utcnow_naive()
        session.commit()

    return LogoutResponse()


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUserDep) -> User:
    return current_user
