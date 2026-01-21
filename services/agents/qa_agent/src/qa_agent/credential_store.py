"""
Secure credential storage for E2E testing.

Provides encrypted storage and retrieval of web application credentials
for automated browser testing.
"""

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ai_core import get_logger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .browser_config import (
    DEFAULT_CREDENTIAL_ROTATION_DAYS,
    ENCRYPTION_KEY_ENV_VAR,
    SESSION_MAX_AGE_DAYS,
    SESSION_STORAGE_DIR,
)

logger = get_logger(__name__)


@dataclass
class Credential:
    """Decrypted credential data."""

    id: str
    app_name: str
    credential_type: str
    role: str
    username: str
    password: str
    metadata: dict[str, Any] | None
    expires_at: datetime | None
    last_rotated_at: datetime | None


@dataclass
class CredentialInfo:
    """Credential metadata without sensitive data."""

    id: str
    app_name: str
    credential_type: str
    role: str
    username: str
    expires_at: datetime | None
    last_rotated_at: datetime | None
    is_expired: bool
    days_until_expiry: int | None


@dataclass
class SessionInfo:
    """Browser session state metadata."""

    id: str
    session_name: str
    app_name: str
    created_at: datetime
    expires_at: datetime
    is_valid: bool


class EncryptionManager:
    """
    Manages encryption/decryption of credential data.

    Uses Fernet symmetric encryption with a key derived from
    the environment variable or a provided key.
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        key = encryption_key or os.environ.get(ENCRYPTION_KEY_ENV_VAR)
        if not key:
            # Generate a key for development (not recommended for production)
            logger.warning(
                f"No {ENCRYPTION_KEY_ENV_VAR} found, generating ephemeral key. "
                "Credentials will not persist across restarts."
            )
            key = Fernet.generate_key().decode()

        # Derive a proper Fernet key from the provided key
        self._fernet = self._create_fernet(key)

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from a key string."""
        # If it's already a valid Fernet key, use it directly
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            pass

        # Otherwise derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"wyld_credential_store_salt",  # Static salt for deterministic keys
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived_key)

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a string value."""
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt a bytes value to string."""
        return self._fernet.decrypt(ciphertext).decode()

    def encrypt_dict(self, data: dict) -> bytes:
        """Encrypt a dictionary as JSON."""
        return self.encrypt(json.dumps(data))

    def decrypt_dict(self, ciphertext: bytes) -> dict:
        """Decrypt bytes to a dictionary."""
        return json.loads(self.decrypt(ciphertext))


class CredentialStore:
    """
    Encrypted credential storage for E2E testing.

    Stores credentials in PostgreSQL with AES-256 encryption.
    Supports credential rotation and expiration tracking.
    """

    def __init__(
        self,
        db_session_factory,
        encryption_key: str | None = None,
    ) -> None:
        """
        Initialize credential store.

        Args:
            db_session_factory: Async session factory for database access
            encryption_key: Optional encryption key (uses env var if not provided)
        """
        self._db_session_factory = db_session_factory
        self._encryption = EncryptionManager(encryption_key)

    async def store_credential(
        self,
        app_name: str,
        credential_type: str,
        username: str,
        password: str,
        user_id: str,
        role: str = "user",
        metadata: dict | None = None,
        rotation_days: int = DEFAULT_CREDENTIAL_ROTATION_DAYS,
    ) -> str:
        """
        Store an encrypted credential.

        Args:
            app_name: Application name (e.g., "wyld-web")
            credential_type: Type of credential ("basic", "oauth", "api_key")
            username: Username or email
            password: Password or secret
            user_id: Owner user ID
            role: User role ("admin", "user", "guest")
            metadata: Additional credential data
            rotation_days: Days before rotation is recommended

        Returns:
            Credential ID
        """
        # Import here to avoid circular imports
        from database.models.credential import StoredCredential

        # Encrypt sensitive data
        username_encrypted = self._encryption.encrypt(username)
        password_encrypted = self._encryption.encrypt(password)
        metadata_encrypted = (
            self._encryption.encrypt_dict(metadata) if metadata else None
        )

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=rotation_days)

        async with self._db_session_factory() as session:
            credential = StoredCredential(
                app_name=app_name,
                credential_type=credential_type,
                role=role,
                username_encrypted=username_encrypted,
                password_encrypted=password_encrypted,
                metadata_encrypted=metadata_encrypted,
                rotation_days=rotation_days,
                last_rotated_at=datetime.now(timezone.utc),
                expires_at=expires_at,
                user_id=user_id,
                is_active=True,
            )
            session.add(credential)
            await session.commit()
            await session.refresh(credential)

            logger.info(
                "Credential stored",
                credential_id=credential.id,
                app_name=app_name,
                role=role,
            )

            return credential.id

    async def get_credential(
        self,
        app_name: str,
        user_id: str,
        credential_type: str | None = None,
        role: str | None = None,
    ) -> Credential | None:
        """
        Retrieve a credential by app name and optional filters.

        Args:
            app_name: Application name
            user_id: Owner user ID
            credential_type: Optional credential type filter
            role: Optional role filter

        Returns:
            Decrypted Credential or None
        """
        from database.models.credential import StoredCredential

        async with self._db_session_factory() as session:
            query = select(StoredCredential).where(
                StoredCredential.app_name == app_name,
                StoredCredential.user_id == user_id,
                StoredCredential.is_active == True,
            )

            if credential_type:
                query = query.where(StoredCredential.credential_type == credential_type)
            if role:
                query = query.where(StoredCredential.role == role)

            result = await session.execute(query)
            stored = result.scalar_one_or_none()

            if not stored:
                return None

            # Decrypt credential data
            try:
                username = self._encryption.decrypt(stored.username_encrypted)
                password = self._encryption.decrypt(stored.password_encrypted)
                metadata = (
                    self._encryption.decrypt_dict(stored.metadata_encrypted)
                    if stored.metadata_encrypted
                    else None
                )
            except Exception as e:
                logger.error(
                    "Failed to decrypt credential",
                    credential_id=stored.id,
                    error=str(e),
                )
                return None

            return Credential(
                id=stored.id,
                app_name=stored.app_name,
                credential_type=stored.credential_type,
                role=stored.role,
                username=username,
                password=password,
                metadata=metadata,
                expires_at=stored.expires_at,
                last_rotated_at=stored.last_rotated_at,
            )

    async def rotate_credential(
        self,
        credential_id: str,
        new_password: str,
        user_id: str,
    ) -> bool:
        """
        Rotate a credential's password.

        Args:
            credential_id: Credential ID to rotate
            new_password: New password value
            user_id: User ID performing rotation (for authorization)

        Returns:
            True if rotated successfully
        """
        from database.models.credential import StoredCredential

        password_encrypted = self._encryption.encrypt(new_password)
        now = datetime.now(timezone.utc)

        async with self._db_session_factory() as session:
            # Get credential to check ownership and rotation period
            result = await session.execute(
                select(StoredCredential).where(
                    StoredCredential.id == credential_id,
                    StoredCredential.user_id == user_id,
                )
            )
            stored = result.scalar_one_or_none()

            if not stored:
                logger.warning(
                    "Credential not found or unauthorized",
                    credential_id=credential_id,
                )
                return False

            # Calculate new expiration
            expires_at = now + timedelta(days=stored.rotation_days)

            # Update credential
            await session.execute(
                update(StoredCredential)
                .where(StoredCredential.id == credential_id)
                .values(
                    password_encrypted=password_encrypted,
                    last_rotated_at=now,
                    expires_at=expires_at,
                )
            )
            await session.commit()

            logger.info(
                "Credential rotated",
                credential_id=credential_id,
                expires_at=expires_at.isoformat(),
            )

            return True

    async def list_credentials(
        self,
        user_id: str,
        app_name: str | None = None,
        include_expired: bool = False,
    ) -> list[CredentialInfo]:
        """
        List credentials for a user.

        Args:
            user_id: Owner user ID
            app_name: Optional app name filter
            include_expired: Include expired credentials

        Returns:
            List of CredentialInfo (without sensitive data)
        """
        from database.models.credential import StoredCredential

        async with self._db_session_factory() as session:
            query = select(StoredCredential).where(
                StoredCredential.user_id == user_id,
                StoredCredential.is_active == True,
            )

            if app_name:
                query = query.where(StoredCredential.app_name == app_name)

            if not include_expired:
                query = query.where(
                    StoredCredential.expires_at > datetime.now(timezone.utc)
                )

            result = await session.execute(query)
            credentials = result.scalars().all()

            now = datetime.now(timezone.utc)
            infos = []

            for cred in credentials:
                # Decrypt username for info
                try:
                    username = self._encryption.decrypt(cred.username_encrypted)
                except Exception:
                    username = "[decryption failed]"

                is_expired = cred.expires_at and cred.expires_at < now
                days_until_expiry = None
                if cred.expires_at and not is_expired:
                    days_until_expiry = (cred.expires_at - now).days

                infos.append(
                    CredentialInfo(
                        id=cred.id,
                        app_name=cred.app_name,
                        credential_type=cred.credential_type,
                        role=cred.role,
                        username=username,
                        expires_at=cred.expires_at,
                        last_rotated_at=cred.last_rotated_at,
                        is_expired=is_expired,
                        days_until_expiry=days_until_expiry,
                    )
                )

            return infos

    async def delete_credential(
        self,
        credential_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete (deactivate) a credential.

        Args:
            credential_id: Credential ID to delete
            user_id: User ID performing deletion (for authorization)

        Returns:
            True if deleted successfully
        """
        from database.models.credential import StoredCredential

        async with self._db_session_factory() as session:
            result = await session.execute(
                update(StoredCredential)
                .where(
                    StoredCredential.id == credential_id,
                    StoredCredential.user_id == user_id,
                )
                .values(is_active=False)
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info("Credential deleted", credential_id=credential_id)
                return True

            return False


class SessionManager:
    """
    Manage browser session states (cookies, localStorage).

    Saves and loads authenticated session states for reuse
    across test runs.
    """

    def __init__(self, storage_dir: str = SESSION_STORAGE_DIR) -> None:
        self._storage_dir = storage_dir
        self._encryption = EncryptionManager()
        os.makedirs(storage_dir, exist_ok=True)

    def _get_session_path(self, session_id: str) -> str:
        """Get file path for a session."""
        return os.path.join(self._storage_dir, f"{session_id}.session")

    def _get_metadata_path(self, session_id: str) -> str:
        """Get metadata file path for a session."""
        return os.path.join(self._storage_dir, f"{session_id}.meta")

    async def save_session(
        self,
        context,  # BrowserContext
        session_name: str,
        app_name: str,
    ) -> str:
        """
        Save browser context state to file.

        Args:
            context: Playwright BrowserContext
            session_name: Name for this session
            app_name: Application this session is for

        Returns:
            Session ID
        """
        from uuid import uuid4

        session_id = str(uuid4())
        session_path = self._get_session_path(session_id)
        metadata_path = self._get_metadata_path(session_id)

        # Get storage state from context
        storage_state = await context.storage_state()

        # Encrypt and save
        encrypted = self._encryption.encrypt(json.dumps(storage_state))
        with open(session_path, "wb") as f:
            f.write(encrypted)

        # Save metadata
        now = datetime.now(timezone.utc)
        metadata = {
            "id": session_id,
            "session_name": session_name,
            "app_name": app_name,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=SESSION_MAX_AGE_DAYS)).isoformat(),
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        logger.info(
            "Session saved",
            session_id=session_id,
            session_name=session_name,
            app_name=app_name,
        )

        return session_id

    async def load_session(
        self,
        session_id: str,
    ) -> dict | None:
        """
        Load a saved session state.

        Args:
            session_id: Session ID to load

        Returns:
            Storage state dict or None if not found/expired
        """
        session_path = self._get_session_path(session_id)
        metadata_path = self._get_metadata_path(session_id)

        if not os.path.exists(session_path):
            return None

        # Check metadata for expiration
        if os.path.exists(metadata_path):
            with open(metadata_path) as f:
                metadata = json.load(f)

            expires_at = datetime.fromisoformat(metadata["expires_at"])
            if expires_at < datetime.now(timezone.utc):
                logger.info("Session expired", session_id=session_id)
                await self.delete_session(session_id)
                return None

        # Decrypt and return
        with open(session_path, "rb") as f:
            encrypted = f.read()

        try:
            storage_state = json.loads(self._encryption.decrypt(encrypted))
            logger.info("Session loaded", session_id=session_id)
            return storage_state
        except Exception as e:
            logger.error("Failed to load session", session_id=session_id, error=str(e))
            return None

    async def list_sessions(
        self,
        app_name: str | None = None,
    ) -> list[SessionInfo]:
        """
        List saved sessions.

        Args:
            app_name: Optional filter by app name

        Returns:
            List of SessionInfo
        """
        sessions = []
        now = datetime.now(timezone.utc)

        for filename in os.listdir(self._storage_dir):
            if not filename.endswith(".meta"):
                continue

            metadata_path = os.path.join(self._storage_dir, filename)
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)

                if app_name and metadata.get("app_name") != app_name:
                    continue

                created_at = datetime.fromisoformat(metadata["created_at"])
                expires_at = datetime.fromisoformat(metadata["expires_at"])
                is_valid = expires_at > now

                sessions.append(
                    SessionInfo(
                        id=metadata["id"],
                        session_name=metadata["session_name"],
                        app_name=metadata["app_name"],
                        created_at=created_at,
                        expires_at=expires_at,
                        is_valid=is_valid,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read session metadata: {filename}", error=str(e))

        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a saved session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted
        """
        session_path = self._get_session_path(session_id)
        metadata_path = self._get_metadata_path(session_id)
        deleted = False

        for path in [session_path, metadata_path]:
            if os.path.exists(path):
                os.remove(path)
                deleted = True

        if deleted:
            logger.info("Session deleted", session_id=session_id)

        return deleted

    async def cleanup_expired(self) -> int:
        """
        Remove expired sessions.

        Returns:
            Number of sessions removed
        """
        sessions = await self.list_sessions()
        removed = 0

        for session in sessions:
            if not session.is_valid:
                await self.delete_session(session.id)
                removed += 1

        if removed > 0:
            logger.info("Cleaned up expired sessions", count=removed)

        return removed


# Singleton instances
_credential_store: CredentialStore | None = None
_session_manager: SessionManager | None = None


def get_credential_store(db_session_factory=None) -> CredentialStore:
    """Get the singleton CredentialStore instance."""
    global _credential_store
    if _credential_store is None:
        if db_session_factory is None:
            raise ValueError("db_session_factory required for first initialization")
        _credential_store = CredentialStore(db_session_factory)
    return _credential_store


def get_session_manager() -> SessionManager:
    """Get the singleton SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
