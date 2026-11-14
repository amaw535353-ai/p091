"""F-001: routine bootstrap must not restore an administrator-revoked group."""

import pytest
from fastapi.testclient import TestClient

from p091.config import Settings
from p091.main import create_app
from p091.seed import seed_store


def _login(client: TestClient, user_id: str) -> dict[str, str]:
    response = client.post("/lab/login", json={"user_id": user_id})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.mark.parametrize("bootstrap", ["repeat-seed", "restart"])
def test_group_revocation_survives_bootstrap(tmp_path, bootstrap):
    """REVOKE-RESTART-001: durable group removal survives both seed entrypoints."""
    settings = Settings(database_url="sqlite:///" + str(tmp_path / "lab.db"))
    app = create_app(settings)
    document = next(
        d for d in app.state.store.documents()
        if d["group"] == "northwind-hr"
        and d["owner"] != "nw-employee"
        and not d["deleted"]
    )
    url = "/documents/" + document["id"]
    with TestClient(app) as client:
        employee = _login(client, "nw-employee")
        admin = _login(client, "nw-admin")
        assert client.get(url, headers=employee).status_code == 200
        removed = client.patch(
            "/admin/groups/northwind-hr/members/nw-employee",
            headers=admin,
            json={"member": False},
        )
        assert removed.status_code == 200
        assert client.get(url, headers=employee).status_code == 404
        assert "northwind-hr" not in client.get("/auth/me", headers=employee).json()["groups"]
        if bootstrap == "repeat-seed":
            seed_store(app.state.store)
            assert "northwind-hr" not in client.get("/auth/me", headers=employee).json()["groups"]
            assert client.get(url, headers=employee).status_code == 404
            # A durable denial must not be implemented by disabling all reads.
            assert client.post("/search", headers=employee, json={"query": "welcome"}).json()["documents"]
            return

    restarted = create_app(settings)
    with TestClient(restarted) as client:
        employee = _login(client, "nw-employee")
        assert "northwind-hr" not in client.get("/auth/me", headers=employee).json()["groups"]
        assert client.get(url, headers=employee).status_code == 404
        assert client.post("/search", headers=employee, json={"query": "welcome"}).json()["documents"]
