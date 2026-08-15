from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Protocol

import keyring
from cryptography.fernet import Fernet, InvalidToken
from keyring.errors import KeyringError

from backend.app.config.defaults import CREDENTIAL_KEY, CREDENTIAL_SERVICE
from backend.app.database.repositories import CredentialsRepository
from backend.app.paths import ensure_work_dirs


class KeyringBackend(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def get_password(self, service: str, username: str) -> str | None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class EncryptedFileBackend:
    """Small encrypted credential backend for headless Linux containers."""

    def __init__(self, path: Path, secret: str):
        if len(secret) < 16:
            raise RuntimeError("DNS_SWITCHER_SESSION_TOKEN deve contenere almeno 16 caratteri")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self.fernet = Fernet(key)
        self.path = path

    def set_password(self, service: str, username: str, password: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.fernet.encrypt(password.encode("utf-8")).decode("ascii")
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"service": service, "username": username, "password": encrypted}),
            encoding="utf-8",
        )
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.path)

    def get_password(self, service: str, username: str) -> str | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("service") != service or data.get("username") != username:
                return None
            return self.fernet.decrypt(str(data["password"]).encode("ascii")).decode("utf-8")
        except (OSError, ValueError, KeyError, InvalidToken, json.JSONDecodeError) as exc:
            raise KeyringError("Archivio credenziali cifrato non leggibile") from exc

    def delete_password(self, service: str, username: str) -> None:
        if self.get_password(service, username) is not None:
            self.path.unlink(missing_ok=True)


def default_backend() -> KeyringBackend:
    if os.getenv("DNS_SWITCHER_CONTAINER", "0") == "1":
        secret = os.getenv("DNS_SWITCHER_CREDENTIAL_KEY") or os.getenv("DNS_SWITCHER_SESSION_TOKEN", "")
        path = ensure_work_dirs()["data"] / "router_credentials.enc"
        return EncryptedFileBackend(path, secret)
    return keyring


class CredentialStore:
    """Stores the router password in the platform-specific protected backend."""

    def __init__(self, repository: CredentialsRepository, backend: KeyringBackend | None = None):
        self.repository = repository
        self.backend = backend or default_backend()

    def save(self, username: str, password: str | None) -> None:
        username = username.strip()
        if not username:
            raise ValueError("Il nome utente del router è obbligatorio")
        current = self.repository.get()
        if password:
            try:
                self.backend.set_password(CREDENTIAL_SERVICE, CREDENTIAL_KEY, password)
            except KeyringError as exc:
                raise RuntimeError("L'archivio protetto delle credenziali non è disponibile") from exc
        elif not current or not self.has_password():
            raise ValueError("Inserire la password al primo salvataggio")
        self.repository.save_reference(username, CREDENTIAL_KEY)

    def get(self) -> tuple[str, str]:
        record = self.repository.get()
        if not record:
            raise RuntimeError("Credenziali router non configurate")
        try:
            password = self.backend.get_password(CREDENTIAL_SERVICE, record["credential_ref"])
        except KeyringError as exc:
            raise RuntimeError("Impossibile leggere l'archivio protetto delle credenziali") from exc
        if not password:
            raise RuntimeError("Password router non presente nell'archivio protetto")
        return record["username"], password

    def has_password(self) -> bool:
        record = self.repository.get()
        if not record:
            return False
        try:
            return self.backend.get_password(CREDENTIAL_SERVICE, record["credential_ref"]) is not None
        except KeyringError:
            return False

    def public_status(self) -> dict[str, object]:
        record = self.repository.get()
        return {
            "username": record["username"] if record else "admin",
            "password_configured": self.has_password(),
        }
