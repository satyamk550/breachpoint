import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_user
from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.models.config import Config
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenResponse,
    UserResponse,
)
from app.services.sessions import create_session, delete_all_sessions, delete_session

router = APIRouter(prefix="/auth", tags=["auth"])


async def enforce_limit(redis: Redis, key: str, limit: int, window: int) -> None:
    pipe = redis.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, window)
    count, _ = await pipe.execute()
    if int(count) > limit:
        retry_after = await redis.ttl(key)
        error = HTTPException(status_code=429, detail="Too many requests")
        error.headers = {"Retry-After": str(max(1, retry_after))}
        raise error


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.session_ttl_seconds,
    )


async def registration_is_open(session: AsyncSession) -> bool:
    config = await session.get(Config, "registration_open")
    return config is None or config.value.casefold() == "true"


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> User:
    await enforce_limit(
        redis,
        f"rate:register:ip:{get_client_ip(request)}",
        settings.register_ip_limit,
        settings.register_window_seconds,
    )
    if not await registration_is_open(session):
        raise HTTPException(status_code=403, detail="Registration is closed")
    username = payload.username.strip()
    email = str(payload.email).strip().casefold()
    existing = await session.scalar(
        select(User).where(
            (func.lower(User.username) == username.casefold()) | (func.lower(User.email) == email)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already taken")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(username=username, email=email, password_hash=password_hash, role="player")
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username or email already taken") from None
    await session.refresh(user)
    set_session_cookie(response, await create_session(redis, user.id))
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> User:
    await enforce_limit(
        redis,
        f"rate:login:ip:{get_client_ip(request)}",
        settings.login_ip_limit,
        settings.login_window_seconds,
    )
    await enforce_limit(
        redis,
        f"rate:login:user:{payload.username.casefold()}",
        settings.login_username_limit,
        settings.login_window_seconds,
    )
    user = await session.scalar(
        select(User).where(func.lower(User.username) == payload.username.casefold())
    )
    valid = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, payload.password)
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account unavailable")
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    set_session_cookie(response, await create_session(redis, user.id))
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, redis: Redis = Depends(get_redis)) -> None:
    await delete_session(redis, request.cookies.get("session_id"))
    response.delete_cookie("session_id")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(require_user)) -> User:
    return user


@router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> None:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await delete_all_sessions(redis, user.id)
    response.delete_cookie("session_id")


@router.post("/admin/users/{user_id}/reset-token", response_model=ResetTokenResponse)
async def create_reset_token(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ResetTokenResponse:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    raw_token = new_token()
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    session.add(
        PasswordResetToken(
            user_id=user_id, token_hash=token_digest(raw_token), expires_at=expires_at
        )
    )
    await session.commit()
    return ResetTokenResponse(user_id=user_id, token=raw_token, expires_at=expires_at)


@router.post("/reset-password", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> None:
    reset = await session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_digest(payload.token)
        )
    )
    now = datetime.now(UTC)
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    try:
        password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = await session.get(User, reset.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = password_hash
    reset.used_at = now
    await session.commit()
    await delete_all_sessions(redis, user.id)
