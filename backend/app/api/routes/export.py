import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.note import Note
from app.models.route import Route
from app.models.saved_lead import SavedLead
from app.models.user import User
from app.services.lead_service import fetch_leads
router = APIRouter()


@router.get("/routes/{route_id}/leads.csv")
async def export_route_leads_csv(
    route_id: UUID,
    saved_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:

    route = (await db.execute(select(Route).where(Route.id == route_id, Route.user_id == user.id))).scalar_one_or_none()
    if not route:
        return StreamingResponse(iter(["route not found\n"]), media_type="text/plain", status_code=404)

    leads, _, _ = await fetch_leads(db, route_id=route_id, min_score=0, limit=2000, offset=0)

    saved_ids: set[UUID] = set()
    if saved_only:
        rows = (
            await db.execute(
                select(SavedLead.business_id).where(SavedLead.user_id == user.id, SavedLead.route_id == route_id)
            )
        ).all()
        saved_ids = {row[0] for row in rows}

    notes_rows = (
        await db.execute(
            select(Note.business_id, Note.note_text).where(Note.user_id == user.id, Note.route_id == route_id)
        )
    ).all()
    notes_by_business: dict[UUID, list[str]] = {}
    for business_id, note_text in notes_rows:
        notes_by_business.setdefault(business_id, []).append(note_text)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "address", "phone", "website", "insurance_class", "final_score", "distance_m", "status", "notes"])

    for lead in leads:
        bid = lead["business_id"]
        if saved_only and bid not in saved_ids:
            continue
        status = "saved" if bid in saved_ids else ""
        writer.writerow(
            [
                lead["name"],
                lead["address"] or "",
                lead["phone"] or "",
                lead["website"] or "",
                lead["insurance_class"] or "",
                lead["final_score"],
                int(lead["distance_from_route_m"]),
                status,
                "; ".join(notes_by_business.get(bid, [])),
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="route_{route_id}_leads.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
