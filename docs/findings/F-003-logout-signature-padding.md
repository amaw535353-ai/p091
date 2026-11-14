# F-003 — Equivalent JWT signature encoding bypassed logout revocation

**Classification:** confirmed implementation defect, remediated and retested. **Severity:** Medium in this synthetic laboratory. **Risk:** #1 identity/session handling. A successful reproduction required possession of an otherwise valid synthetic token. No signing-key compromise, identity escalation or third-party service vulnerability was demonstrated.

## Observation and root cause

The API's process-local logout denylist originally keyed revocation by the SHA-256 of the serialized bearer token. The JWT verifier accepted equivalent Base64URL encodings of the signature: appending `=` to the signature portion preserved the verified signature and claims while changing the raw token string.

After logout, the original serialization was denied but an equivalent padded serialization remained authorized. The failed boundary was between authenticated token identity and its transport representation. A holder of the token could defeat the API's stated same-process logout revocation until normal expiration. The already documented limitation that revocation is volatile across live-process restarts is separate and was not required for this reproduction.

## Measured before evidence

Evidence ID: **F-003-BEFORE**. Observed with the actual offline FastAPI application and TestClient on **2026-11-14T20:18:26Z**, using only in-memory synthetic data. No token strings were retained. Pre-fix `p091/auth.py` SHA-256:

```text
ba5917ce4f33a087b11dfacbc214725d91b756a0b16002af3b1ab4e3f32d6eb8
```

Exact local command:

```sh
.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from p091.config import Settings
from p091.main import create_app
app = create_app(Settings(database_url='sqlite:///:memory:'))
with TestClient(app) as c:
    token = c.post('/lab/login', json={'user_id':'nw-employee'}).json()['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    padded_headers = {'Authorization': 'Bearer ' + token + '='}
    print('before', c.get('/auth/me', headers=headers).status_code)
    print('logout', c.post('/auth/logout', headers=headers).status_code)
    print('same_token_after_logout', c.get('/auth/me', headers=headers).status_code)
    print('equivalent_signature_padding_after_logout', c.get('/auth/me', headers=padded_headers).status_code)
PY
```

Observed stdout before the fix, exit 0:

```text
before 200
logout 200
same_token_after_logout 401
equivalent_signature_padding_after_logout 200
```

The authentication implementation agent independently repeated the same statuses at **2026-11-14T20:20:09.744135Z**, with the same pre-fix source hash. Its sanitized before/after evidence is retained in `../evidence/F003-auth-revocation.json` (evidence ID **E-F003-AUTH-REVOCATION**).

## Remediation

The verifier now checks cryptographic validity, trusted issuer/audience, time bounds and required typed claims before consulting token-supplied revocation identity. It derives a stable denylist key from the **verified issuer and jti** and checks/revokes that identity. Equivalent signature encodings therefore share the same decision. An unsigned or incorrectly signed token cannot poison the denylist by copying another token's jti. Expired denylist entries are pruned.

The change deliberately preserves the lab's existing process-local storage boundary. A durable shared session/revocation store and provider-session introspection remain separate production requirements.

## Measured retest

At **2026-11-14T20:21:35.407971Z**, the implementation agent observed allowed original access (200), successful logout (200), then **401** for the original serialization and each of the `=`, `==` and `===` signature-padding variants. Post-fix `p091/auth.py` SHA-256:

```text
2e249974a46095ec1410bb2ac69cbb06725bc06dbfb54313d66a106b953c1df6
```

Regression file: `tests/unit/test_auth_revocation.py`.

| Test ID | Verified purpose | Cases |
| --- | --- | --- |
| AUTH-LOGOUT-001 | Logout blocks equivalent signature-padding variants on identity and document routes | 3 |
| AUTH-LOGOUT-002 | Forged same-jti token neither authorizes nor revokes a valid identity | 1 |
| AUTH-LOGOUT-003 | Identity revocation is consistent in a mocked trusted-JWKS path | 1 |
| AUTH-LOGOUT-004 | Expired revocation entries are pruned without denying a valid unrelated token | 1 |

Executed command and observed result reported by the implementation agent:

```sh
.venv/bin/python -m pytest tests/unit/test_auth_revocation.py -q
# 6 passed, 1 warning in 1.42s; exit 0
```

The retained evidence also records the combined adapter/regression command:

```sh
.venv/bin/python -m pytest tests/unit/test_auth_revocation.py tests/unit/test_adapters.py -q
# 55 passed, 1 Starlette deprecation warning; exit 0
```

The trusted-JWKS regression uses `httpx.MockTransport`; it does not establish that Keycloak was deployed or that provider logout/introspection works. Findings and counts refer to these explicit configurations and test cases. Relate this finding to the project's session-handling requirement; do not inflate it into complete ASVS session compliance or a claim about all token libraries.
