# F-004 — Content-only reindex cleared unknown authorization state

**Classification:** confirmed application policy defect under a mocked source, remediated and retested. **Severity:** Medium in the synthetic lab. **Risks:** #1 workload identity separation and #3 connector/RAG permissions. **Supporting projects:** P-031 permission inheritance and P-037 synchronization. This is an application observation with the real `NextcloudSource` adapter and simulated HTTP responses; it is **not** a finding against a running Nextcloud service.

## Failed boundary and impact

The `acl_known` flag makes uncertainty a denial condition in the server's document-access gate. Before the fix, `Services.reindex` set that flag to true after fetching content, even though the WebDAV response proved only that the connector account could read the file. It did not establish a current end-user authorization graph.

A workload principal with only the ingestion scope could therefore clear an independent authorization uncertainty while indexing content. In the exercised state, an employee's read changed from denied to allowed after an indexer reindex, without a trusted ACL reconciliation or administrator decision. The failure joined a content-ingestion boundary to the authority required to certify access policy.

Severity is Medium for this local synthetic system: the test required an existing ACL-unknown record plus a valid ingestion identity, and no production data was involved. A deployment using the same uncertainty flag during source-policy errors would need to assess its own impact and reachability separately.

## Measured before evidence

Evidence ID: **F-004-BEFORE**. Execution used the actual FastAPI application, SQLite, synthetic employee/indexer tokens, actual `NextcloudSource` parsing, and `httpx.MockTransport` responses. The fixture selected an HR document the employee could otherwise read, then set its authoritative ACL certainty to false while preserving matching source/index versions. The simulated WebDAV metadata returned `G`, a current ETag, a text MIME type and a bounded length; no user/group ACL proof was supplied.

Recorded before-fix source SHA-256 on **2026-11-14T20:20:23Z**:

```text
c500882f18309b055698948e781e2a064750140869e7926aa6e938bccb88dba0  p091/services.py
```

Exact local reproduction command, printing no credentials:

```sh
.venv/bin/python - <<'PY'
import httpx
from fastapi.testclient import TestClient
from p091.adapters import NextcloudSource
from p091.config import Settings
from p091.main import create_app
settings = Settings(database_url='sqlite:///:memory:', nextcloud_enabled=True, nextcloud_user='connector')
app = create_app(settings)
doc = next(d for d in app.state.store.documents() if d['group'] == 'northwind-hr' and d['owner'] != 'nw-employee' and not d['deleted'])
app.state.store.update_document(doc['id'], source_version='"v1"', synced_version='"v1"', acl_known=False)
metadata = ('<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:response><d:propstat><d:prop><d:getetag>"v1"</d:getetag><d:getcontentlength>' + str(len(doc['body'].encode())) + '</d:getcontentlength><d:getcontenttype>text/plain</d:getcontenttype><oc:permissions>G</oc:permissions></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>').encode()
def handler(request):
    return httpx.Response(207, content=metadata) if request.method == 'PROPFIND' else httpx.Response(200, content=doc['body'].encode())
app.state.services.source = NextcloudSource(settings, httpx.Client(transport=httpx.MockTransport(handler)))
with TestClient(app) as c:
    employee={'Authorization':'Bearer ' + c.post('/lab/login', json={'user_id':'nw-employee'}).json()['access_token']}
    indexer={'Authorization':'Bearer ' + app.state.auth.issue_lab_token('nw-indexer','northwind',actor_type='service',scopes='ingest')}
    print('read_acl_unknown', c.get('/documents/' + doc['id'], headers=employee).status_code)
    print('service_reindex', c.post('/ingestion/reindex/' + doc['id'], headers=indexer).status_code)
    print('acl_known_after_content_only_reindex', app.state.store.get_document(doc['id'])['acl_known'])
    print('read_after_content_only_reindex', c.get('/documents/' + doc['id'], headers=employee).status_code)
PY
```

Observed stdout before remediation, exit 0:

```text
read_acl_unknown 404
service_reindex 200
acl_known_after_content_only_reindex True
read_after_content_only_reindex 200
```

## Remediation and retest

Content reindex now updates content/provenance/version and index synchronization only. It preserves `acl_known`; only a future explicit trusted ACL-reconciliation mechanism may clear an unknown authorization state. Such a reconciliation mechanism is currently absent, so uncertainty continues to deny access.

Evidence ID: **F-004-RETEST**. Regression: `tests/integration/test_source_acl_state.py::test_content_reindex_preserves_independent_acl_state`, Test ID **SOURCE-ACL-001**, parameterized for known and unknown ACLs. The unknown case proves that the indexer can refresh content while the employee remains denied. The known case preserves an authorized useful read. Both use actual adapter parsing with mocked source transport and require no external requests.

Executed commands:

```sh
.venv/bin/python -m pytest -q tests/integration/test_source_acl_state.py
.venv/bin/ruff check tests/integration/test_source_acl_state.py
.venv/bin/mypy tests/integration/test_source_acl_state.py
```

Observed results, all exit 0:

```text
2 passed, 1 warning in 1.98s
All checks passed!
Success: no issues found in 1 source file
```

The warning was the installed Starlette/TestClient deprecation notice. Post-fix source hash recorded **2026-11-14T20:21:03Z**:

```text
67c7d7d11d445d4e934f39ab414eec1c45b8954e3fa80518bfd15e8ea06d8c28  p091/services.py
```

## Applicability and limits

Related requirements: **AISVS 1.0 5.2.2** (end-user authorization through retrieval/assembly), **ASVS v5.0.0-8.3.1** (trusted enforcement), and workload least privilege. See `../requirements/standards-references.md` for verified source identifiers.

This retest establishes the application's treatment of an already unknown ACL under simulated source HTTP. It does not establish how a live Nextcloud ACL is reconciled, whether external source share changes set this flag, or a defect in Nextcloud. Complete source ACL synchronization remains an explicit project limitation. Reindexing content cannot substitute for that missing authority.
