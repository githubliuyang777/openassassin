from sqlalchemy.orm import Session

from app.models.script import Script
from app.schemas.script import ScriptCreate, ScriptUpdate


def list_scripts(db: Session, page: int = 1, page_size: int = 20, search: str = ""):
    q = db.query(Script)
    if search:
        q = q.filter(Script.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Script.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_script(db: Session, script_id: int) -> Script | None:
    return db.query(Script).filter(Script.id == script_id).first()


def create_script(db: Session, data: ScriptCreate) -> Script:
    script = Script(**data.model_dump())
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def update_script(db: Session, script: Script, data: ScriptUpdate) -> Script:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(script, k, v)
    db.commit()
    db.refresh(script)
    return script


def delete_script(db: Session, script: Script) -> None:
    db.delete(script)
    db.commit()
