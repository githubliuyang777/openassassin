from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.notepad import Notepad
from app.schemas.notepad import NotepadCreate, NotepadUpdate
from app.services import batch_service


def list_notepads(db: Session, page: int = 1, page_size: int = 20, search: str = "") -> dict:
    query = db.query(Notepad)
    if search:
        kw = f"%{search}%"
        query = query.filter(or_(Notepad.title.ilike(kw), Notepad.content.ilike(kw)))
    total = query.count()
    items = (
        query.order_by(Notepad.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_notepad(db: Session, notepad_id: int) -> Notepad | None:
    return db.query(Notepad).filter(Notepad.id == notepad_id).first()


def create_notepad(db: Session, data: NotepadCreate) -> Notepad:
    notepad = Notepad(**data.model_dump())
    db.add(notepad)
    db.commit()
    db.refresh(notepad)
    return notepad


def update_notepad(db: Session, notepad: Notepad, data: NotepadUpdate) -> Notepad:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(notepad, field, value)
    db.commit()
    db.refresh(notepad)
    return notepad


def delete_notepads(db: Session, ids: list[int]) -> tuple[int, list[int]]:
    deleted, missing = batch_service.delete_rows(db, Notepad, ids)
    db.commit()
    return deleted, missing


def delete_notepad(db: Session, notepad: Notepad) -> None:
    delete_notepads(db, [notepad.id])
