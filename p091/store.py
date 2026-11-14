"""Small SQL repository. Values are parameterized and migrations run transactionally."""
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, database_url: str):
        self.lock = threading.RLock()
        self.faults: set[str] = set()
        self.postgres = database_url.startswith("postgresql://")
        self.db: Any
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            self.db = psycopg.connect(database_url, row_factory=dict_row, autocommit=True)
        else:
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")
        with self.transaction():
            script = (Path(__file__).parent / "migrations/001_initial.sql").read_text()
            for statement in script.split(";"):
                if statement.strip():
                    self.execute(statement)

    def execute(self, sql: str, params: tuple = ()) -> Any:
        return self.db.execute(sql.replace("?", "%s") if self.postgres else sql, params)

    def transaction(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def scope():
            with self.lock:
                self.execute("BEGIN")
                try:
                    yield
                    self.execute("COMMIT")
                except BaseException:
                    self.execute("ROLLBACK")
                    raise
        return scope()

    def users(self) -> list[dict]:
        return [user for row in self.execute("SELECT user_id FROM users ORDER BY user_id").fetchall() if (user := self.get_user(row["user_id"])) is not None]

    def get_user(self, user_id: str) -> dict | None:
        row = self.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        user = dict(row)
        user["id"] = user.pop("user_id")
        user["admin"] = bool(user["admin"])
        user["groups"] = [r["group_id"] for r in self.execute("SELECT group_id FROM memberships WHERE user_id=? ORDER BY group_id", (user_id,)).fetchall()]
        return user

    def documents(self) -> list[dict]:
        return [doc for r in self.execute("SELECT id FROM documents ORDER BY id").fetchall() if (doc := self.get_document(r["id"])) is not None]

    def get_document(self, doc_id: str) -> dict | None:
        row = self.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return None
        doc = dict(row)
        doc["group"] = doc.pop("group_id")
        doc["deleted"], doc["acl_known"] = bool(doc["deleted"]), bool(doc["acl_known"])
        doc["readers"] = [r["user_id"] for r in self.execute("SELECT user_id FROM grants WHERE document_id=? ORDER BY user_id", (doc_id,)).fetchall()]
        return doc

    def update_document(self, doc_id: str, **fields: Any) -> None:
        allowed = {"tenant", "title", "body", "visibility", "group", "owner", "version", "source_version", "synced_version", "deleted", "acl_known", "source_path"}
        if not fields or set(fields) - allowed:
            raise ValueError("Unknown document field")
        with self.lock:
            for key, value in fields.items():
                column = "group_id" if key == "group" else key
                if isinstance(value, bool):
                    value = int(value)
                self.execute(f"UPDATE documents SET {column}=? WHERE id=?", (value, doc_id))

    def set_membership(self, group: str, user_id: str, member: bool) -> None:
        with self.lock:
            if member:
                self.execute("INSERT INTO memberships(group_id,user_id) VALUES (?,?) ON CONFLICT DO NOTHING", (group, user_id))
            else:
                self.execute("DELETE FROM memberships WHERE group_id=? AND user_id=?", (group, user_id))

    def set_shared(self, doc_id: str, user_id: str, member: bool) -> None:
        with self.lock:
            if member:
                self.execute("INSERT INTO grants(document_id,user_id) VALUES (?,?) ON CONFLICT DO NOTHING", (doc_id, user_id))
            else:
                self.execute("DELETE FROM grants WHERE document_id=? AND user_id=?", (doc_id, user_id))

    def save_message(self, user_id: str, question: str, refs: list[dict]) -> str:
        ident = str(uuid.uuid4())
        self.execute("INSERT INTO messages(id,user_id,question,refs) VALUES (?,?,?,?)", (ident, user_id, question, json.dumps(refs)))
        return ident

    def messages(self, user_id: str) -> list[dict]:
        rows = self.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
        return [dict(r) | {"refs": json.loads(r["refs"])} for r in rows]

    def audit(self, correlation_id: str, sub: str, actor_type: str, action: str, outcome: str, source_version: str | None = None) -> None:
        # Never store question text, document titles/content, auth headers or tokens here.
        self.execute("INSERT INTO audits VALUES (?,?,?,?,?,?,?,?,?)", (
            str(uuid.uuid4()), correlation_id, hashlib.sha256(sub.encode()).hexdigest()[:16], actor_type,
            action, outcome, "p091-policy-v1", source_version, datetime.now(UTC).isoformat(),
        ))

    def set_fault(self, name: str, enabled: bool) -> None:
        if enabled:
            self.faults.add(name)
        else:
            self.faults.discard(name)

    def close(self) -> None:
        self.db.close()
