import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


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
