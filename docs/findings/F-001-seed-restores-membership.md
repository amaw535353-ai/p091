# F-001 — Repeated seed restored revoked group access

**Classification:** confirmed implementation defect, remediated and retested. **Severity:** Medium in this owned synthetic laboratory. **Risk:** #3 connector/RAG permissions and #35 user isolation. **Supporting projects:** P-031 permission inheritance and P-037 revocation. This was observed in the default offline application; it is not a deliberately vulnerable fixture or evidence of a third-party product vulnerability.

## Observation and impact

The normal startup path calls `seed_store`. Before the fix, the user insert used `ON CONFLICT DO NOTHING`, but fixture group memberships were inserted for every user regardless of whether that user already existed. Removing an employee from HR correctly denied access immediately. Restarting the application against the same database then silently recreated the removed HR membership, restoring document access.

An authorized administrator's revocation therefore failed to survive routine startup or an explicit repeated seed. The affected boundary was persisted authorization state versus bootstrap defaults. The impact was unauthorized renewed access to synthetic department-restricted documents after a lifecycle action. No real data or outside system was involved. Severity is Medium because it required a local application restart/reseed after a legitimate revocation; the observed access restoration was material but confined to the demonstration lab.

## Measured before evidence

Evidence ID: **F-001-BEFORE**. A local tempfile SQLite database and `fastapi.testclient.TestClient` were used; no externally reachable service was started. Evidence recorded immediately after reproduction on **2026-11-14T20:15:44Z**. No Git commit existed. SHA-256 of the pre-fix `p091/seed.py`, captured before remediation:

```text
39db3359c5a92ab0a1a049d42c57f4ebe26f75ede6658293517f156ca5aa0ba3
```

The exact command below uses tokens only in process memory and prints no credentials:

```sh
.venv/bin/python - <<'PY'
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from p091.config import Settings
from p091.main import create_app
with tempfile.TemporaryDirectory(prefix='p091-review-') as td:
    settings = Settings(database_url='sqlite:///' + str(Path(td) / 'lab.db'))
    app = create_app(settings)
    doc = next(d for d in app.state.store.documents() if d['group'] == 'northwind-hr' and d['owner'] != 'nw-employee' and not d['deleted'])
    with TestClient(app) as c:
        admin = {'Authorization': 'Bearer ' + c.post('/lab/login', json={'user_id': 'nw-admin'}).json()['access_token']}
        user = {'Authorization': 'Bearer ' + c.post('/lab/login', json={'user_id': 'nw-employee'}).json()['access_token']}
        print('before_remove', c.get('/documents/' + doc['id'], headers=user).status_code)
        print('remove', c.patch('/admin/groups/northwind-hr/members/nw-employee', headers=admin, json={'member': False}).status_code)
        print('after_remove', c.get('/documents/' + doc['id'], headers=user).status_code)
    app2 = create_app(settings)
    with TestClient(app2) as c:
        user = {'Authorization': 'Bearer ' + c.post('/lab/login', json={'user_id': 'nw-employee'}).json()['access_token']}
        print('after_restart_groups', c.get('/auth/me', headers=user).json()['groups'])
        print('after_restart_read', c.get('/documents/' + doc['id'], headers=user).status_code)
PY
```

Observed stdout before the fix, process exit 0:

```text
before_remove 200
remove 200
after_remove 404
after_restart_groups ['northwind-hr']
after_restart_read 200
```

The run also emitted an installed Starlette/TestClient deprecation warning. No pre-fix pytest run is claimed: the original observation used the explicit reproduction above.

## Remediation and measured retest

User seeding now captures the user insert's affected-row count and initializes group memberships only for a newly created user. Existing user memberships, including administrator removals, remain authoritative. Document-reader seeding already had an equivalent new-record guard. Explicit destructive lab reset remains a separate operator action.

Regression: `tests/integration/test_seed_restart.py::test_group_revocation_survives_bootstrap`, parameterized for **repeat-seed** and **restart**. Test ID: **REVOKE-RESTART-001**. Both cases check an initially allowed HR read, successful administrator removal, subsequent denied read, preserved absence of membership after bootstrap, and a still-working permitted welcome search.

Evidence ID: **F-001-RETEST**. Executed after the root agent's remediation:

```sh
.venv/bin/python -m pytest -q tests/integration/test_seed_restart.py
.venv/bin/ruff check tests/integration/test_seed_restart.py
.venv/bin/mypy tests/integration/test_seed_restart.py
```

Observed results:

```text
2 passed, 1 warning in 0.88s
All checks passed!
Success: no issues found in 1 source file
```

All three commands exited 0. The warning was the same TestClient deprecation warning, not a test failure. Post-fix source hash recorded **2026-11-14T20:16:46Z**:

```text
eb78a7426fa95b4d4dbd197f0502c175fdec2798a4bb96180ab4664764c3bbb9  p091/seed.py
```

## Standards and limits

Related verified requirement: **ASVS v5.0.0-8.3.2**, immediate application of authorization changes. Related AISVS context: **1.0 5.2.2**, end-user authorization throughout retrieval/assembly. See `../requirements/standards-references.md` for official sources; these links do not imply full-standard compliance.

The measured reproduction and retest used persistent SQLite and the offline identity path. The same shared seed function is used for PostgreSQL, but this finding does not claim a live PostgreSQL/Keycloak/OpenFGA restart measurement. It does not establish distributed revocation consistency, complete Nextcloud source-ACL synchronization, or durable provider-session revocation. Re-run the regression after bootstrap/seed changes and include it in the normal suite.
