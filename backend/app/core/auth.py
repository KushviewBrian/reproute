from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwk, jwt
from jose.utils import base64url_decode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User


@dataclass
class AuthUser:
    id: str
    email: str


@lru_cache
def _cached_jwks_fetcher() -> dict:
    return {}


async def _get_jwks(jwks_url: str) -> dict:
    cache = _cached_jwks_fetcher()
    if cache.get("url") == jwks_url and cache.get("keys"):
        return {"keys": cache["keys"]}

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        payload = resp.json()
    cache["url"] = jwks_url
    cache["keys"] = payload.get("keys", [])
    return {"keys": cache["keys"]}


async def _verify_token_signature(token: str, jwks_url: str) -> None:
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token key id")

    jwks = await _get_jwks(jwks_url)
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signing key not found")

    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode("utf-8"))
    key = jwk.construct(key_data)
    if not key.verify(message.encode("utf-8"), decoded_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    settings = get_settings()

    try:
        if settings.clerk_jwks_url:
            await _verify_token_signature(token, settings.clerk_jwks_url)
        claims = jwt.get_unverified_claims(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    issuer = claims.get("iss")
    if settings.clerk_jwt_issuer and issuer and settings.clerk_jwt_issuer.rstrip("/") != issuer.rstrip("/"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")

    email = claims.get("email") or claims.get("primary_email_address")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email")

    full_name = (claims.get("name") or "").strip() or None

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    user = User(email=email, full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
