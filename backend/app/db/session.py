from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        from app.core.config import get_settings
        settings = get_settings()
        # statement_cache_size=0 required for Supabase pgbouncer pooler
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args = {"timeout": 10, "command_timeout": 10, "ssl": ssl_ctx, "statement_cache_size": 0}
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=2,
            connect_args=connect_args,
        )
        _SessionLocal = async_sessionmaker(
            bind=_engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine, _SessionLocal


# Expose engine for the debug endpoint
@property
def engine():
    e, _ = _get_engine()
    return e


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, SessionLocal = _get_engine()
    async with SessionLocal() as session:
        yield session
