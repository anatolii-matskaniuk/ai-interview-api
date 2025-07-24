from fastapi import Depends, HTTPException, status, APIRouter, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, oauth2_scheme
from src.auth.models import User
from src.auth.schemas import UserPublic, UserCreate, Token
from src.auth.service import AuthService, TokenService
from src.db.session import get_db

router = APIRouter()
auth_service = AuthService()
token_service = TokenService()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await auth_service.create(db=db, user_data=user_data)


@router.post("/login", response_model=Token)
async def login_for_access_token(
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    user = await auth_service.authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = token_service.create_access_token(user_id=user.id)
    refresh_token = await token_service.create_refresh_token(db, user_id=user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=True
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: str = Depends(oauth2_scheme)):
    await token_service.blacklist_token(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
        response: Response,
        refresh_token_value: str | None = Cookie(default=None, alias="refresh_token"),
        db: AsyncSession = Depends(get_db)
):
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    rotated_token_data = await token_service.rotate_refresh_token(
        db,
        token_value=refresh_token_value,
    )
    if not rotated_token_data:
        response.delete_cookie("refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    new_refresh_token_id, user_id = rotated_token_data
    new_access_token = token_service.create_access_token(user_id=user_id)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token_id,
        httponly=True,
        samesite="lax",
        secure=True
    )
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserPublic)
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user
