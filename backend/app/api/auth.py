"""Authentication endpoints (Google OAuth + JWT)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class GoogleTokenRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    """Verify a JWT and return its payload."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def _get_or_create_user(db: AsyncSession, email: str, display_name: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=display_name, major="Computer Science")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange Google OAuth ID token for a JWT session.

    1. Verify the Google ID token
    2. Extract email, check @terpmail.umd.edu domain
    3. Create or fetch user from database
    4. Return JWT access token
    """
    if settings.demo_mode:
        user = await _get_or_create_user(db, "demo@terpmail.umd.edu", "Demo Student")
        token = _create_jwt(str(user.id), user.email)
        return AuthResponse(
            access_token=token,
            user={"id": str(user.id), "email": user.email, "display_name": user.display_name},
        )

    # Verify Google ID token
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={body.id_token}"
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            token_info = resp.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=401, detail="Failed to verify Google token")

    email = token_info.get("email", "")
    if not email.endswith("@terpmail.umd.edu") and not email.endswith("@umd.edu"):
        raise HTTPException(status_code=403, detail="Only UMD email addresses are allowed")

    display_name = token_info.get("name", email.split("@")[0])

    user = await _get_or_create_user(db, email, display_name)
    access_token = _create_jwt(str(user.id), user.email)

    return AuthResponse(
        access_token=access_token,
        user={"id": str(user.id), "email": user.email, "display_name": user.display_name},
    )


@router.post("/logout")
async def logout():
    """Invalidate the current session (client-side token discard)."""
    return {"message": "Logged out successfully"}
