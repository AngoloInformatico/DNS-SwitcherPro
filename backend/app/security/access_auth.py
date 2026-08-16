from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time

from backend.app.database.repositories import AccessPasswordRepository


class AccessPasswordManager:
    """Hashes and verifies the password used to open the application."""

    ITERATIONS = 600_000
    MIN_LENGTH = 8
    MAX_LENGTH = 128

    def __init__(self, repository: AccessPasswordRepository):
        self.repository = repository
        self._lock = threading.RLock()

    def is_configured(self) -> bool:
        return self.repository.get() is not None

    def set_initial(self, password: str) -> None:
        with self._lock:
            if self.is_configured():
                raise ValueError("La password di accesso è già configurata")
            self._save(password)

    def change(self, current_password: str, new_password: str) -> None:
        with self._lock:
            if not self.verify(current_password):
                raise PermissionError("La password attuale non è corretta")
            if secrets.compare_digest(current_password, new_password):
                raise ValueError("La nuova password deve essere diversa da quella attuale")
            self._save(new_password)

    def verify(self, password: str) -> bool:
        with self._lock:
            record = self.repository.get()
            if not record:
                return False
            try:
                salt = base64.b64decode(str(record["salt"]), validate=True)
                expected = base64.b64decode(str(record["password_hash"]), validate=True)
                iterations = int(record["iterations"])
            except (KeyError, TypeError, ValueError):
                return False
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return secrets.compare_digest(actual, expected)

    def _save(self, password: str) -> None:
        if len(password) < self.MIN_LENGTH:
            raise ValueError(f"La password deve contenere almeno {self.MIN_LENGTH} caratteri")
        if len(password) > self.MAX_LENGTH:
            raise ValueError(f"La password non può superare {self.MAX_LENGTH} caratteri")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.ITERATIONS)
        self.repository.save(
            base64.b64encode(digest).decode("ascii"),
            base64.b64encode(salt).decode("ascii"),
            self.ITERATIONS,
        )


class AccessSessionStore:
    COOKIE_NAME = "dns_switcher_access"
    TTL_SECONDS = 12 * 60 * 60

    def __init__(self) -> None:
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            self._sessions[token] = now + self.TTL_SECONDS
        return token

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return token in self._sessions

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _prune(self, now: float) -> None:
        expired = [token for token, expiry in self._sessions.items() if expiry <= now]
        for token in expired:
            self._sessions.pop(token, None)
