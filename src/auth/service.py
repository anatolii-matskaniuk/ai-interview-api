import uuid
from datetime import timezone, datetime, timedelta

from fastapi import HTTPException, status
from jose import jwt, JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, RefreshToken
from src.auth.schemas import UserCreate
from src.auth.utils import get_password_hash, verify_password
from src.core.config import settings


class AuthService:
    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).filter(User.email == email))
        return result.scalars().first()

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await db.get(User, user_id)

    async def create(self, db: AsyncSession, user_data: UserCreate) -> User:
        if await self.get_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        hashed_password = get_password_hash(user_data.password)
        new_user = User(email=user_data.email, hashed_password=hashed_password)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> User | None:
        user = await self.get_by_email(db, email)
        if not user or not verify_password(password, user.hashed_password) or not user.is_active:
            return None
        return user


class TokenService:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def create_access_token(self, user_id: uuid.UUID) -> str:
        expire = datetime.now(timezone.utc) + \
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"sub": str(user_id), "exp": int(expire.timestamp())}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def create_refresh_token(self, db: AsyncSession, user_id: uuid.UUID) -> str:
        refresh_token = RefreshToken(user_id=user_id)
        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)
        return str(refresh_token.id)

    async def get_refresh_token(self, db: AsyncSession, token: str) -> RefreshToken | None:
        try:
            token_uuid = uuid.UUID(token)
            return await db.get(RefreshToken, token_uuid)
        except (ValueError, TypeError):
            return None

    async def blacklist_token(self, token: str):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                                 options={"verify_exp": False})
            expires = payload.get("exp")
            if expires:
                time_to_expire = datetime.fromtimestamp(
                    expires, tz=timezone.utc) - datetime.now(timezone.utc)
                if time_to_expire.total_seconds() > 0:
                    await self.redis_client.set(f"blacklist:{token}", "true", ex=time_to_expire)
        except JWTError:
            pass

    async def is_token_blacklisted(self, token: str) -> bool:
        return await self.redis_client.get(f"blacklist:{token}") is not None

    async def rotate_refresh_token(
            self, db: AsyncSession, token_value: str) -> tuple[RefreshToken, str]:
        refresh_token = await self.get_refresh_token(db, token=token_value)
        if not refresh_token or refresh_token.expires_at < datetime.now(timezone.utc):
            if refresh_token:
                await db.delete(refresh_token)
                await db.commit()
            return None
        user_id = refresh_token.user_id
        await db.delete(refresh_token)
        new_refresh_token_id = await self.create_refresh_token(db, user_id=user_id)
        return new_refresh_token_id, user_id
