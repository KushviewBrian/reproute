from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import func, select

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.db.session import _get_engine
from app.models.import_job import ImportJob
from app.models.user import User
from app.schemas.import_job import ImportJobItem, StartOvertureImportRequest

router = APIRouter()


def _require_admin_secret(admin_secret: str | None) -> None:
    settings = get_settings()
    configured = (settings.admin_import_secret or "").strip()
    if configured:
        if admin_secret != configured:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin secret")
        return
    if settings.is_production():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin import disabled")


def _require_admin_email(user: User) -> None:
    settings = get_settings()
    allowlist = settings.admin_allowed_email_set()
    user_email = (user.email or "").strip().lower()
    if settings.is_production() and not allowlist:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin allowlist not configured",
        )
    if allowlist and user_email not in allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an admin")


def _validate_parquet_path(parquet_path: str) -> str:
    settings = get_settings()
    candidate = Path(parquet_path).expanduser().resolve()
    roots = settings.admin_import_allowed_root_paths()
    if settings.is_production() and not roots:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin import roots not configured",
        )
    if roots:
        allowed = False
        for root in roots:
            try:
                candidate.relative_to(root)
                allowed = True
                break
            except ValueError:
                continue
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parquet path is outside allowed import roots",
            )
    return str(candidate)


def _sync_database_url(payload_db_url: str | None) -> str:
    settings = get_settings()
    raw = (payload_db_url or settings.ingest_database_url or settings.database_url).strip()
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return raw


async def _update_job(
    job_id: UUID,
    *,
    status_value: str,
    error_message: str | None = None,
    result_json: dict | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    _, session_local = _get_engine()
    async with session_local() as db:
        job = await db.get(ImportJob, job_id)
        if not job:
            return
        job.status = status_value
        job.error_message = error_message
        if result_json is not None:
            job.result_json = result_json
        now = datetime.now(timezone.utc)
        if started:
            job.started_at = now
        if finished:
            job.finished_at = now
        await db.commit()


async def _run_import_job(job_id: UUID, parquet_path: str, database_url: str) -> None:
    await _update_job(job_id, status_value="running", started=True)

    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "scripts" / "ingest_overture.py"
    if not script_path.exists():
        await _update_job(
            job_id,
            status_value="failed",
            error_message=f"Script not found: {script_path}",
            finished=True,
        )
        return

    cmd = [
        sys.executable,
        str(script_path),
        "--parquet",
        parquet_path,
        "--database-url",
        database_url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60 * 60,
            cwd=str(repo_root),
        )
    except subprocess.TimeoutExpired:
        await _update_job(
            job_id,
            status_value="failed",
            error_message="Import timed out after 60 minutes",
            finished=True,
        )
        return
    except Exception as exc:
        await _update_job(
            job_id,
            status_value="failed",
            error_message=f"Import process failed: {exc}",
            finished=True,
        )
        return

    stdout_tail = (proc.stdout or "")[-4000:]
    stderr_tail = (proc.stderr or "")[-4000:]
    result_json = {
        "returncode": proc.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "command": cmd,
    }

    if proc.returncode == 0:
        await _update_job(
            job_id,
            status_value="done",
            result_json=result_json,
            finished=True,
        )
    else:
        await _update_job(
            job_id,
            status_value="failed",
            error_message=f"Ingest script exited with code {proc.returncode}",
            result_json=result_json,
            finished=True,
        )


@router.post("/overture", response_model=ImportJobItem)
async def start_overture_import(
    payload: StartOvertureImportRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> ImportJobItem:
    _require_admin_secret(admin_secret)
    _require_admin_email(user)
    resolved_parquet_path = _validate_parquet_path(payload.parquet_path)

    db_url = _sync_database_url(payload.database_url)
    _, session_local = _get_engine()
    async with session_local() as db:
        running_count = await db.scalar(
            select(func.count())
            .select_from(ImportJob)
            .where(ImportJob.status.in_(("queued", "running")))
        )
        if int(running_count or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another import job is already running",
            )
        job = ImportJob(
            user_id=user.id,
            source_type="overture_parquet",
            parquet_path=resolved_parquet_path,
            label=payload.label,
            bbox=payload.bbox,
            status="queued",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    background_tasks.add_task(_run_import_job, job.id, resolved_parquet_path, db_url)
    return ImportJobItem(
        id=job.id,
        user_id=job.user_id,
        source_type=job.source_type,
        parquet_path=job.parquet_path,
        label=job.label,
        bbox=job.bbox,
        status=job.status,
        error_message=job.error_message,
        result_json=job.result_json,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/jobs/{job_id}", response_model=ImportJobItem)
async def get_import_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> ImportJobItem:
    _require_admin_secret(admin_secret)
    _require_admin_email(user)
    _ = user
    _, session_local = _get_engine()
    async with session_local() as db:
        job = await db.get(ImportJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
        return ImportJobItem(
            id=job.id,
            user_id=job.user_id,
            source_type=job.source_type,
            parquet_path=job.parquet_path,
            label=job.label,
            bbox=job.bbox,
            status=job.status,
            error_message=job.error_message,
            result_json=job.result_json,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
