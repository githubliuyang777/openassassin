from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.notepad import NotepadCreate, NotepadUpdate, NotepadResponse
from app.services import notepad_service

router = APIRouter(prefix="/notepads", tags=["notepads"])


@router.get("")
def list_notepads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notepad_service.list_notepads(db, page, page_size, search)


@router.get("/{notepad_id}", response_model=NotepadResponse)
def get_notepad(
    notepad_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    n = notepad_service.get_notepad(db, notepad_id)
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记事本不存在")
    return n


@router.post("", response_model=NotepadResponse, status_code=status.HTTP_201_CREATED)
def create_notepad(
    data: NotepadCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notepad_service.create_notepad(db, data)


@router.put("/{notepad_id}", response_model=NotepadResponse)
def update_notepad(
    notepad_id: int,
    data: NotepadUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    n = notepad_service.get_notepad(db, notepad_id)
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记事本不存在")
    return notepad_service.update_notepad(db, n, data)


@router.delete("/{notepad_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notepad(
    notepad_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    n = notepad_service.get_notepad(db, notepad_id)
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记事本不存在")
    notepad_service.delete_notepad(db, n)
