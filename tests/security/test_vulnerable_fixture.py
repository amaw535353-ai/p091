"""Safe before/fix/after contrast. Fixture vulnerability is not an API finding."""
import pytest
from fastapi.testclient import TestClient

from fixtures.vulnerable_demo import unsafe_lookup
from p091.config import Settings
from p091.main import create_app


def test_vulnerable_fixture_disabled_without_explicit_opt_in():
    with pytest.raises(RuntimeError, match="disabled"):
        unsafe_lookup([], "synthetic")


def test_before_after_authoritative_tenant_gate():
    app = create_app(Settings(database_url="sqlite:///:memory:"))
    with TestClient(app) as client:
        docs = app.state.store.documents()
        before = unsafe_lookup(docs, "CO_FINANCE_CANARY", allow_vulnerable_fixture=True)
        assert len(before) == 1 and before[0]["tenant"] == "contoso"
        token = client.post("/lab/login", json={"user_id": "nw-employee"}).json()["access_token"]
        after = client.post("/search", json={"query": "CO_FINANCE_CANARY"}, headers={"Authorization": "Bearer " + token})
        assert after.status_code == 200 and after.json()["documents"] == []
