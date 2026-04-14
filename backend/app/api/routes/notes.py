from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.note import Note
from app.models.user import User
from app.schemas.note import CreateNoteRequest, NoteItem, UpdateNoteRequest

router = APIRouter()


@router.post("", response_model=NoteItem)
async def create_note(
    payload: CreateNoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteItem:
    note = Note(
        user_id=user.id,
        business_id=payload.business_id,
        route_id=payload.route_id,
        note_text=payload.note_text,
        outcome_status=payload.outcome_status,
        next_action=payload.next_action,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    return NoteItem(
        id=note.id,
        business_id=note.business_id,
        route_id=note.route_id,
        note_text=note.note_text,
        outcome_status=note.outcome_status,
        next_action=note.next_action,
        created_at=note.created_at,
    )


@router.get("", response_model=list[NoteItem])
async def get_notes(
    business_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteItem]:
    rows = (
        await db.execute(
            select(Note)
            .where(Note.user_id == user.id, Note.business_id == business_id)
            .order_by(desc(Note.created_at))
        )
    ).scalars().all()

    return [
        NoteItem(
            id=n.id,
            business_id=n.business_id,
            route_id=n.route_id,
            note_text=n.note_text,
            outcome_status=n.outcome_status,
            next_action=n.next_action,
            created_at=n.created_at,
        )
        for n in rows
    ]


@router.patch("/{note_id}", response_model=NoteItem)
async def update_note(
    note_id: UUID,
    payload: UpdateNoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteItem:
    note = (await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if payload.note_text is not None:
        note.note_text = payload.note_text
    if payload.outcome_status is not None:
        note.outcome_status = payload.outcome_status
    if payload.next_action is not None:
        note.next_action = payload.next_action

    await db.commit()
    await db.refresh(note)
    return NoteItem(
        id=note.id,
        business_id=note.business_id,
        route_id=note.route_id,
        note_text=note.note_text,
        outcome_status=note.outcome_status,
        next_action=note.next_action,
        created_at=note.created_at,
    )
