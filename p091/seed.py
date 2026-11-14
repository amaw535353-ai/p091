"""Idempotent synthetic seed; resetting requires an explicit, separate command."""
import json
from pathlib import Path

from p091.config import Settings
from p091.store import Store

ROOT = Path(__file__).resolve().parent.parent


def seed_store(store: Store) -> None:
    data = json.loads((ROOT / "fixtures/synthetic-data/seed.json").read_text())
    with store.transaction():
        for u in data["users"]:
            created_user = store.execute("INSERT INTO users VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING", (u["id"], u["tenant"], u["department"], int(u["admin"]), u["actor_type"]))
            if created_user.rowcount:
                for group in u["groups"]:
                    store.execute("INSERT INTO memberships VALUES (?,?) ON CONFLICT DO NOTHING", (group, u["id"]))
        for d in data["documents"]:
            created = store.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING", (
                d["id"], d["tenant"], d["title"], d["body"], d["visibility"], d.get("group"), d["owner"],
                1, "1", "1", int(d.get("deleted", False)), int(d.get("acl_known", True)), d["source_path"],
            ))
            # Seeding must never restore a previously revoked grant.
            if created.rowcount:
                for user_id in d.get("readers", []):
                    store.set_shared(d["id"], user_id, True)


if __name__ == "__main__":
    store = Store(Settings.from_env().database_url)
    seed_store(store)
    print(f"Seed ready: {len(store.users())} synthetic identities, {len(store.documents())} documents")
    store.close()
