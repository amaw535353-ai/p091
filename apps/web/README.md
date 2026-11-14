# Local lab interface and browser verification

The FastAPI app serves this directory at `/assets` and `index.html` at `/`.
The interface uses no remote fonts, images, scripts or analytics. Untrusted
document titles, bodies, quotes and errors are inserted with `textContent`.
Bearer credentials are held only in page memory. Live sign-in uses Keycloak's
authorization-code flow with S256 PKCE and validates the callback state; only the
temporary state and verifier are placed in `sessionStorage` before redirect.

Every response is bound to the session epoch that started it. Logout clears the
current rendered data and input values; late responses and their error/finally
handlers cannot repopulate a different user's session. See confirmed finding
`docs/findings/F-002-browser-session-race.md` and the before/retest artifacts.

Optional real-browser checks require Python Playwright and a local Chromium
executable. In the observed environment the system Python supplied Playwright,
`/usr/bin/chromium` supplied Chromium, and the API used `.venv/bin/python`:

```sh
python apps/web/check_browser.py
python apps/web/check_session_race.py
```

Both commands start a temporary offline API on a loopback ephemeral port and
stop it afterward. Browser screenshots and exact measured checks are retained
under `docs/evidence/ui`. The first checks permitted retrieval/citations,
identity switching, literal hostile markup, logout cleanup, browser storage and
the mobile layout. The second deliberately holds authenticated responses across
logout and another tenant's login, then verifies normal retrieval still works.

With the real lab Keycloak service running and `.env` prepared:

```sh
python apps/web/check_keycloak.py
```

This checks real human logins for employees/admins in both tenants using PKCE,
actual JWKS JWT verification and in-process app token revocation. It temporarily
serves the registered `http://localhost:8000/` callback, so it does not
claim that the PostgreSQL-backed live application ran end to end. It reads only
the synthetic lab password from `.env`, never logs it, and retains no tokens.
See `docs/evidence/live/keycloak-human.json` after execution. The verifier must
reject human tokens missing `sub`; the realm has an explicit `oidc-sub-mapper`
because replacing Keycloak's default scopes otherwise omits its `basic` mapper.
