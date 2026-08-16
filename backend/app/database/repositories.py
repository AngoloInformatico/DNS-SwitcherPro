from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .connection import Database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SettingsRepository:
    def __init__(self, database: Database):
        self.database = database

    def all(self) -> dict[str, str]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_many(self, values: dict[str, str]) -> None:
        now = utc_now()
        with self.database.connect() as connection:
            connection.executemany(
                """INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                [(key, value, now) for key, value in values.items()],
            )


class CredentialsRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self) -> dict[str, str] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT username, credential_ref FROM router_credentials WHERE id=1"
            ).fetchone()
        return dict(row) if row else None

    def save_reference(self, username: str, credential_ref: str) -> None:
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO router_credentials(id, username, credential_ref, created_at, updated_at)
                VALUES(1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET username=excluded.username,
                    credential_ref=excluded.credential_ref, updated_at=excluded.updated_at""",
                (username, credential_ref, now, now),
            )


class AccessPasswordRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT password_hash, salt, iterations FROM access_password WHERE id=1"
            ).fetchone()
        return dict(row) if row else None

    def save(self, password_hash: str, salt: str, iterations: int) -> None:
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO access_password(
                    id, password_hash, salt, iterations, created_at, updated_at
                ) VALUES(1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash,
                    salt=excluded.salt, iterations=excluded.iterations,
                    updated_at=excluded.updated_at""",
                (password_hash, salt, iterations, now, now),
            )


class HistoryRepository:
    def __init__(self, database: Database):
        self.database = database

    def start(self, mode: str, dns_ip: str) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO operation_history(mode, dns_ip, started_at, status) VALUES(?, ?, ?, 'running')",
                (mode, dns_ip, utc_now()),
            )
            return int(cursor.lastrowid)

    def finish(self, operation_id: int, status: str, message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE operation_history SET completed_at=?, status=?, message=? WHERE id=?",
                (utc_now(), status, message, operation_id),
            )

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM operation_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
