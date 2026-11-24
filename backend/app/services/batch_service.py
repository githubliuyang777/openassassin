from sqlalchemy.orm import Session


def delete_rows(db: Session, model, ids: list[int]) -> tuple[int, list[int]]:
    """Delete rows by id and report ids that did not exist.

    Does not commit; callers own the transaction so parent/child cleanup is atomic.
    """
    ids = list(dict.fromkeys(ids))
    existing = [
        row_id
        for (row_id,) in db.query(model.id).filter(model.id.in_(ids)).all()
    ]
    if existing:
        db.query(model).filter(model.id.in_(existing)).delete(synchronize_session=False)
    existing_set = set(existing)
    return len(existing), [row_id for row_id in ids if row_id not in existing_set]
