# F-002 — A delayed response crossed a browser session change

**Confirmed and remediated. Severity: Medium in the local shared-browser lab.**
Boundary: an authenticated server response → the browser's currently active
identity. Risks #4/#35; supporting P-029/P-017. This was a browser disclosure of
a response already authorized for its original requester. It did not bypass
the server's document authorization or expose documents to an unrelated remote
browser.

## Observed reproduction

An independent reviewer signed in as the Northwind employee, asked `HR handbook`,
and used Playwright to hold the successful `/chat` response. After signing out
and signing in as the Contoso employee, releasing the old response rendered
`NW_HR_CANARY` under the Contoso identity. The measured output and exact original
source hash are retained in `docs/evidence/ui/race-before.json`.

This matters on a shared browser or when an operator switches tenant identities
while requests are pending. Delayed document details, history, search or error
responses could also overwrite the new session's display. The reproduction
requires access to a previous authenticated browser session and a delayed
response; it is not a cross-tenant API object authorization vulnerability.

## Cause and fix

The browser retained a single mutable token but did not bind asynchronous
requests to the session that initiated them. Logout cleared the current DOM,
yet old success handlers could repopulate it later.

`apps/web/app.js` now increments a session epoch when a session ends. Every API
request checks its initiating epoch before and after asynchronous response
processing. Async loaders, OIDC completion, error handlers and finalizers also
check that epoch before updating state or the DOM. An old 401 response cannot
log out a new session. Logout clears user-entered questions, searches and admin
form values in addition to source, preview, answer and identity text.

## Retest

Run `python apps/web/check_session_race.py` after installing Playwright and
Chromium. It starts an isolated offline API, holds original authorized responses
across a tenant switch, and verifies both absence of old-session text and normal
Contoso retrieval afterward. Cases cover chat success/error, search, document
listing, preview, citation, history listing/detail and dashboard responses.
The current measured denominator and outcome are recorded in
`docs/evidence/ui/race-retest.json`; no result is implied without that artifact.

Residual limits: the browser cannot retract bytes already delivered to someone
who was authorized when they received them. This fix isolates subsequent UI
updates when accounts change; it is not browser memory zeroization or a
replacement for server-side authorization. Multi-tab/session coordination is
not implemented, and each tab must explicitly sign out.
