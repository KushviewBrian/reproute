from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StartOvertureImportRequest(BaseModel):
    parquet_path: str
    label: str | None = None
    bbox: str | None = None
    database_url: str | None = None


class ImportJobItem(BaseModel):
    id: UUID
    user_id: UUID | None
    source_type: str
    parquet_path: str | None
    label: str | None
    bbox: str | None
    status: str
    error_message: str | None = None
    result_json: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
