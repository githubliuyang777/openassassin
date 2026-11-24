import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.credential import Credential
from app.models.host import Host
from app.services import batch_service


class CredentialInUseError(ValueError):
    def __init__(self, host_count: int):
        self.host_count = host_count
        super().__init__(f"{host_count} 台主机仍引用该密钥")


def _get_key() -> bytes:
    key = settings.master_key.encode()
    if len(key) < 32:
        key = key.ljust(32, b"0")
    return key[:32]


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    cipher = AESGCM(_get_key())
    ct = cipher.encrypt(nonce, plaintext.encode(), None)
    return nonce.hex() + ":" + ct.hex()


def decrypt(payload: str) -> str:
    nonce_hex, ct_hex = payload.split(":", 1)
    nonce = bytes.fromhex(nonce_hex)
    ct = bytes.fromhex(ct_hex)
    cipher = AESGCM(_get_key())
    return cipher.decrypt(nonce, ct, None).decode()


def delete_credentials(db: Session, ids: list[int]) -> tuple[int, list[int]]:
    ids = list(dict.fromkeys(ids))
    existing = [
        row_id
        for (row_id,) in db.query(Credential.id).filter(Credential.id.in_(ids)).all()
    ]
    if not existing:
        return 0, ids
    host_count = (
        db.query(Host)
        .filter(or_(
            Host.credential_id.in_(existing),
            Host.aws_credential_id.in_(existing),
        ))
        .count()
    )
    if host_count:
        raise CredentialInUseError(host_count)
    deleted, _ = batch_service.delete_rows(db, Credential, existing)
    db.commit()
    existing_set = set(existing)
    return deleted, [row_id for row_id in ids if row_id not in existing_set]
