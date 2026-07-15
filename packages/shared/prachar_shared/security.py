from __future__ import annotations

import hashlib
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_MARKERS = ("change-me",)


def _derive_key() -> bytes:
    settings = get_settings()
    raw = settings.token_enc_key
    if any(m in raw for m in _PLACEHOLDER_MARKERS):
        raise RuntimeError(
            "TOKEN_ENC_KEY is still the placeholder; set a real secret before encrypting tokens."
        )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_token(plaintext: str) -> bytes:
    """Encrypt a token string with AES-GCM. Returns nonce(12) + ciphertext bytes."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = AESGCM.generate_nonce(bit_length=96)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct


def decrypt_token(ciphertext: bytes) -> str:
    """Decrypt AES-GCM ciphertext (nonce-prefixed) back to plaintext string."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce, ct = ciphertext[:12], ciphertext[12:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
