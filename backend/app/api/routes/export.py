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
from app.models.business import Business
from app.models.saved_lead import SavedLead
from app.models.user import User
from app.services.lead_service import fetch_leads
from app.utils.rate_limit import enforce_rate_limit
router = APIRouter()


@router.get("/routes/{route_id}/leads.csv")
async def export_route_leads_csv(
    route_id: UUID,
    saved_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await enforce_rate_limit(f"rl:export:{user.id}", limit=20, window_seconds=3600)

    route = await db.get(Route, route_id)
    if not route or route.user_id != user.id:
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


@router.get("/saved-leads.csv")
async def export_saved_leads_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await enforce_rate_limit(f"rl:export:{user.id}", limit=20, window_seconds=3600)
    saved_rows = (
        await db.execute(
            select(
                SavedLead,
                Business.name,
                Business.phone,
                Business.address_line1,
                Business.city,
                Business.state,
                Business.postal_code,
                Business.external_source,
            )
            .join(Business, Business.id == SavedLead.business_id, isouter=True)
            .where(SavedLead.user_id == user.id)
            .order_by(SavedLead.created_at.desc())
        )
    ).all()

    business_ids = [row.SavedLead.business_id for row in saved_rows]
    note_rows = []
    if business_ids:
        note_rows = (
            await db.execute(
                select(Note.business_id, Note.note_text)
                .where(Note.user_id == user.id, Note.business_id.in_(business_ids))
                .order_by(Note.business_id, Note.created_at.desc())
            )
        ).all()

    notes_by_business: dict[UUID, list[str]] = {}
    for business_id, note_text in note_rows:
        notes_by_business.setdefault(business_id, []).append(note_text)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "first_name",
            "last_name",
            "company",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "zip",
            "source",
            "status",
            "notes",
        ]
    )
    for row in saved_rows:
        notes = "; ".join(notes_by_business.get(row.SavedLead.business_id, []))
        writer.writerow(
            [
                "",
                "",
                row.name or "",
                row.phone or "",
                "",
                row.address_line1 or "",
                row.city or "",
                row.state or "",
                row.postal_code or "",
                row.external_source or "",
                row.SavedLead.status,
                notes,
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="saved_leads_export.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
