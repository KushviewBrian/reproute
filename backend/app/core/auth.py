from __future__ import annotations

from datetime import datetime, timezone
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

# In-memory cache: email -> User (avoids a DB round-trip on every request)
_user_cache: dict[str, User] = {}


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
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        if settings.clerk_jwks_url:
            await _verify_token_signature(token, settings.clerk_jwks_url)
        claims = jwt.get_unverified_claims(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    issuer = claims.get("iss")
    if settings.clerk_jwt_issuer and issuer and settings.clerk_jwt_issuer.rstrip("/") != issuer.rstrip("/"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")

    exp = claims.get("exp")
    if exp is not None and float(exp) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    email = claims.get("email") or claims.get("primary_email_address")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email")

    # Return cached user if we've seen this email before
    if email in _user_cache:
        return _user_cache[email]

    full_name = (claims.get("name") or "").strip() or None

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        _user_cache[email] = existing
        return existing

    user = User(email=email, full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    _user_cache[email] = user
    return user
