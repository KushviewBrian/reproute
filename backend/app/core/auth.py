from __future__ import annotations

from datetime import datetime, timezone
from collections import OrderedDict
from functools import lru_cache
from time import time

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwk, jwt
from jose.utils import base64url_decode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

_JWKS_CACHE_TTL_SECONDS = 60 * 60
_USER_CACHE_TTL_SECONDS = 5 * 60
_USER_CACHE_MAX_ENTRIES = 500
_user_cache: OrderedDict[str, tuple[User, float]] = OrderedDict()


@lru_cache
def _cached_jwks_fetcher() -> dict:
    return {"url": "", "keys": [], "expires_at": 0.0}


async def _get_jwks(jwks_url: str) -> dict:
    now = time()
    cache = _cached_jwks_fetcher()
    if (
        cache.get("url") == jwks_url
        and cache.get("keys")
        and float(cache.get("expires_at", 0.0)) > now
    ):
        return {"keys": cache["keys"]}

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        payload = resp.json()
    cache["url"] = jwks_url
    cache["keys"] = payload.get("keys", [])
    cache["expires_at"] = now + _JWKS_CACHE_TTL_SECONDS
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


def _get_cached_user(email: str) -> User | None:
    entry = _user_cache.get(email)
    if not entry:
        return None
    user, expires_at = entry
    if expires_at <= time():
        _user_cache.pop(email, None)
        return None
    _user_cache.move_to_end(email)
    return user


def _cache_user(email: str, user: User) -> None:
    _user_cache[email] = (user, time() + _USER_CACHE_TTL_SECONDS)
    _user_cache.move_to_end(email)
    while len(_user_cache) > _USER_CACHE_MAX_ENTRIES:
        _user_cache.popitem(last=False)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        if settings.should_verify_jwt_signature():
            jwks_url = settings.clerk_jwks_url.strip()
            if not jwks_url:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="JWT verification misconfigured",
                )
            await _verify_token_signature(token, jwks_url)
        claims = jwt.get_unverified_claims(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    issuer = claims.get("iss")
    expected_issuer = settings.clerk_jwt_issuer.strip()
    if settings.should_verify_jwt_signature():
        if not expected_issuer:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT issuer misconfigured",
            )
        if not issuer or expected_issuer.rstrip("/") != str(issuer).rstrip("/"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")
    elif expected_issuer and issuer and expected_issuer.rstrip("/") != str(issuer).rstrip("/"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")

    # Optional strict checks when configured
    if settings.clerk_audience:
        aud = claims.get("aud")
        allowed = False
        if isinstance(aud, str):
            allowed = aud == settings.clerk_audience
        elif isinstance(aud, list):
            allowed = settings.clerk_audience in aud
        if not allowed:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")

    if settings.clerk_authorized_party:
        azp = claims.get("azp")
        if azp != settings.clerk_authorized_party:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token authorized party")

    exp = claims.get("exp")
    if exp is not None and float(exp) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    # Use email if present, fall back to Clerk's sub (user ID)
    email = claims.get("email") or claims.get("primary_email_address") or claims.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing identity")

    # Return cached user if we've seen this identity before
    cached_user = _get_cached_user(email)
    if cached_user:
        return cached_user

    full_name = (claims.get("name") or "").strip() or None

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        _cache_user(email, existing)
        return existing

    user = User(email=email, full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    _cache_user(email, user)
    return user
