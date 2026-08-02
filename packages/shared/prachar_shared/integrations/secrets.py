"""Secrets Management — encrypted credential storage, token rotation, expiry monitoring.

Every connected account has:
- Encrypted credentials (access tokens, refresh tokens, API keys)
- Token rotation history
- Expiry monitoring with alerts
- Permission scopes
- Last successful sync / last failed sync
- Refresh history

This is the operational maturity layer. Credentials are never stored in
plaintext. The encryption key comes from the environment (JWT_SECRET or
a dedicated INTEGRATION_ENCRYPTION_KEY).

Usage:
    vault = SecretsVault(encryption_key=os.environ["INTEGRATION_ENCRYPTION_KEY"])

    # Store credentials
    vault.store("conn_123", CredentialBundle(
        access_token="ya29.xxx",
        refresh_token="1//xxx",
        expires_at=datetime(2026, 8, 1, tzinfo=utc),
        scopes=["analytics.readonly"],
    ))

    # Retrieve credentials (auto-decrypts)
    creds = vault.retrieve("conn_123")
    if creds and creds.is_expired():
        # Refresh token...
        vault.store("conn_123", new_creds)
        vault.record_refresh("conn_123", success=True)

    # Check expiry
    expiring = vault.expiring_within(hours=24)
    for conn_id in expiring:
        log.warning("Token %s expires soon", conn_id)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets as pysecrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger("prachar.integrations.secrets")


# ─── Credential Bundle ──────────────────────────────────────────────────────


@dataclass
class CredentialBundle:
    """A bundle of credentials for a single connection.

    Stored encrypted in the vault. Never logged or exposed in API responses.
    """
    access_token: str = ""
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
    # Additional metadata (e.g. Shopify shop domain, Mailchimp DC)
    metadata: dict[str, Any] = field(default_factory=dict)
    # When these credentials were stored
    stored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the access token has expired."""
        if not self.expires_at:
            return False  # No expiry = permanent (e.g. Shopify tokens)
        now = now or datetime.now(timezone.utc)
        return now >= self.expires_at

    def expires_within(self, hours: int = 24, now: datetime | None = None) -> bool:
        """Check if the token will expire within the given hours."""
        if not self.expires_at:
            return False
        now = now or datetime.now(timezone.utc)
        threshold = now + timedelta(hours=hours)
        return self.expires_at <= threshold

    def time_until_expiry(self, now: datetime | None = None) -> timedelta | None:
        """Time remaining until token expires. None if no expiry."""
        if not self.expires_at:
            return None
        now = now or datetime.now(timezone.utc)
        return self.expires_at - now

    def to_dict(self, include_tokens: bool = False) -> dict[str, Any]:
        """Convert to dict. Tokens are excluded by default for safety."""
        d: dict[str, Any] = {
            "scopes": self.scopes,
            "metadata": self.metadata,
            "stored_at": self.stored_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
            "has_refresh_token": self.refresh_token is not None,
        }
        if include_tokens:
            d["access_token"] = self.access_token
            d["refresh_token"] = self.refresh_token
        return d


# ─── Refresh History Entry ──────────────────────────────────────────────────


@dataclass
class RefreshRecord:
    """A single token refresh attempt."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = False
    error: str = ""
    old_expiry: datetime | None = None
    new_expiry: datetime | None = None


# ─── Connection Health Record ───────────────────────────────────────────────


@dataclass
class ConnectionHealthRecord:
    """Operational health for a single connection."""
    connection_id: str
    integration: str
    # Sync tracking
    last_successful_sync: datetime | None = None
    last_failed_sync: datetime | None = None
    last_error: str = ""
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    # Token tracking
    last_refreshed_at: datetime | None = None
    refresh_history: list[RefreshRecord] = field(default_factory=list)
    # Permission scopes (safe to expose)
    permission_scopes: list[str] = field(default_factory=list)

    def record_sync(self, success: bool, error: str = "") -> None:
        """Record a sync attempt."""
        now = datetime.now(timezone.utc)
        self.total_syncs += 1
        if success:
            self.successful_syncs += 1
            self.last_successful_sync = now
            self.last_error = ""
        else:
            self.failed_syncs += 1
            self.last_failed_sync = now
            self.last_error = error

    def record_refresh(self, success: bool, error: str = "",
                       old_expiry: datetime | None = None,
                       new_expiry: datetime | None = None) -> None:
        """Record a token refresh attempt."""
        now = datetime.now(timezone.utc)
        self.last_refreshed_at = now
        self.refresh_history.append(RefreshRecord(
            timestamp=now,
            success=success,
            error=error,
            old_expiry=old_expiry,
            new_expiry=new_expiry,
        ))
        # Keep only last 50 refresh records
        if len(self.refresh_history) > 50:
            self.refresh_history = self.refresh_history[-50:]

    @property
    def success_rate(self) -> float:
        if self.total_syncs == 0:
            return 100.0
        return (self.successful_syncs / self.total_syncs) * 100

    @property
    def last_refresh_success(self) -> bool | None:
        """Was the last refresh successful? None if never refreshed."""
        if not self.refresh_history:
            return None
        return self.refresh_history[-1].success

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "integration": self.integration,
            "last_successful_sync": self.last_successful_sync.isoformat() if self.last_successful_sync else None,
            "last_failed_sync": self.last_failed_sync.isoformat() if self.last_failed_sync else None,
            "last_error": self.last_error,
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "success_rate": round(self.success_rate, 1),
            "last_refreshed_at": self.last_refreshed_at.isoformat() if self.last_refreshed_at else None,
            "last_refresh_success": self.last_refresh_success,
            "refresh_count": len(self.refresh_history),
            "permission_scopes": self.permission_scopes,
        }


# ─── Encryption ─────────────────────────────────────────────────────────────


class CredentialCipher:
    """Simple AES-like encryption for credentials at rest.

    Uses Fernet from the cryptography library if available, otherwise
    falls back to a base64+hash obfuscation (NOT secure, but better than
    plaintext for development).

    In production, use the cryptography library's Fernet or AWS KMS.
    """

    def __init__(self, key: str) -> None:
        self._key = key
        self._fernet = None
        try:
            from cryptography.fernet import Fernet
            # Derive a Fernet-compatible key from the provided key
            key_bytes = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(fernet_key)
        except ImportError:
            log.warning(
                "cryptography library not installed — using obfuscation only. "
                "Install with: pip install cryptography"
            )

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string."""
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode()).decode()
        # Fallback: base64 encode (NOT secure — dev only)
        return base64.b64encode(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string."""
        if self._fernet:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        # Fallback: base64 decode
        return base64.b64decode(ciphertext.encode()).decode()


# ─── Secrets Vault ──────────────────────────────────────────────────────────


class SecretsVault:
    """Encrypted credential vault with token rotation and expiry monitoring.

    Credentials are stored encrypted. The vault tracks:
    - When credentials were stored
    - When they expire
    - Refresh history
    - Sync success/failure

    The vault is designed to be backed by a database in production.
    For development, it uses an in-memory store.
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        key = encryption_key or os.environ.get("INTEGRATION_ENCRYPTION_KEY") or os.environ.get("JWT_SECRET", "dev-only-key")
        self._cipher = CredentialCipher(key)
        # In production, these would be DB-backed
        self._credentials: dict[str, str] = {}  # connection_id → encrypted blob
        self._health: dict[str, ConnectionHealthRecord] = {}

    def store(self, connection_id: str, creds: CredentialBundle) -> None:
        """Store credentials (encrypted) for a connection."""
        # Serialize and encrypt
        import json
        data = {
            "access_token": creds.access_token,
            "refresh_token": creds.refresh_token,
            "expires_at": creds.expires_at.isoformat() if creds.expires_at else None,
            "scopes": creds.scopes,
            "metadata": creds.metadata,
            "stored_at": creds.stored_at.isoformat(),
        }
        encrypted = self._cipher.encrypt(json.dumps(data))
        self._credentials[connection_id] = encrypted

        # Update health record with scopes
        if connection_id not in self._health:
            self._health[connection_id] = ConnectionHealthRecord(
                connection_id=connection_id,
                integration=creds.metadata.get("integration", ""),
            )
        self._health[connection_id].permission_scopes = creds.scopes

    def retrieve(self, connection_id: str) -> CredentialBundle | None:
        """Retrieve and decrypt credentials for a connection."""
        encrypted = self._credentials.get(connection_id)
        if not encrypted:
            return None

        import json
        try:
            data = json.loads(self._cipher.decrypt(encrypted))
            return CredentialBundle(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
                scopes=data.get("scopes", []),
                metadata=data.get("metadata", {}),
                stored_at=datetime.fromisoformat(data["stored_at"]) if data.get("stored_at") else datetime.now(timezone.utc),
            )
        except Exception as e:
            log.error("Failed to decrypt credentials for %s: %s", connection_id, e)
            return None

    def delete(self, connection_id: str) -> None:
        """Delete credentials for a connection."""
        self._credentials.pop(connection_id, None)
        self._health.pop(connection_id, None)

    def record_refresh(self, connection_id: str, success: bool,
                       error: str = "", old_expiry: datetime | None = None,
                       new_expiry: datetime | None = None) -> None:
        """Record a token refresh attempt."""
        if connection_id not in self._health:
            self._health[connection_id] = ConnectionHealthRecord(
                connection_id=connection_id, integration="")
        self._health[connection_id].record_refresh(
            success=success, error=error,
            old_expiry=old_expiry, new_expiry=new_expiry,
        )

    def record_sync(self, connection_id: str, success: bool, error: str = "") -> None:
        """Record a sync attempt."""
        if connection_id not in self._health:
            self._health[connection_id] = ConnectionHealthRecord(
                connection_id=connection_id, integration="")
        self._health[connection_id].record_sync(success=success, error=error)

    def get_health(self, connection_id: str) -> ConnectionHealthRecord | None:
        """Get the health record for a connection."""
        return self._health.get(connection_id)

    def expiring_within(self, hours: int = 24) -> list[str]:
        """Get connection IDs whose tokens expire within the given hours."""
        expiring: list[str] = []
        for conn_id in self._credentials:
            creds = self.retrieve(conn_id)
            if creds and creds.expires_within(hours=hours):
                expiring.append(conn_id)
        return expiring

    def expired(self) -> list[str]:
        """Get connection IDs whose tokens have expired."""
        expired_list: list[str] = []
        for conn_id in self._credentials:
            creds = self.retrieve(conn_id)
            if creds and creds.is_expired():
                expired_list.append(conn_id)
        return expired_list

    def all_health(self) -> list[dict[str, Any]]:
        """Get health records for all connections (for the Integration Centre UI)."""
        return [h.to_dict() for h in self._health.values()]

    def has_credentials(self, connection_id: str) -> bool:
        """Check if credentials exist for a connection."""
        return connection_id in self._credentials


# ─── Singleton ──────────────────────────────────────────────────────────────


_vault: SecretsVault | None = None


def get_secrets_vault() -> SecretsVault:
    """Get the global secrets vault instance."""
    global _vault
    if _vault is None:
        _vault = SecretsVault()
    return _vault
