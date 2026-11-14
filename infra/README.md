# Local integration topology and version record

The topology is for a disposable synthetic lab. Every published port binds only
`127.0.0.1`. Internal traffic is plaintext on the project network; it is not a
production deployment. CPU/memory estimates are planning assumptions: allow
4 CPUs / 6 GiB for core, 4 CPUs / 8–10 GiB for extended and at least 10 GiB disk with an efficient storage driver, or 20 GiB with Docker
`vfs` because it duplicates image layers. No measured capacity benchmark has been performed.

## Pinned components

Official release/image sources checked on 2026-11-14:

| Component | Pin | License | Source | Validation at initial scaffold |
|---|---|---|---|---|
| Python | `python:3.12.16-slim-bookworm` | PSF | [Official image source](https://github.com/docker-library/python/blob/master/3.12/slim-bookworm/Dockerfile) | Version confirmed from source; container not yet run |
| PostgreSQL | `postgres:17.12-bookworm` | PostgreSQL | [Official image source](https://github.com/docker-library/postgres/blob/master/17/bookworm/Dockerfile) | Image extraction blocked by ENOSPC; no PostgreSQL integration result |
| Keycloak | `quay.io/keycloak/keycloak:26.8.2` | Apache-2.0 | [Release](https://github.com/keycloak/keycloak/releases/tag/26.8.2), [container guide](https://www.keycloak.org/server/containers) | Real H2 realm import and 7/7 service/JWKS probes passed; browser PKCE recorded separately |
| OpenFGA | `openfga/openfga:v1.22.1` | Apache-2.0 | [Release](https://github.com/openfga/openfga/releases/tag/v1.22.1), [Docker setup](https://openfga.dev/docs/getting-started/setup-openfga/docker) | Real container accepted model; 2/2 allow/deny probes passed |
| Qdrant | `qdrant/qdrant:v1.20.1` | Apache-2.0 | [Release](https://github.com/qdrant/qdrant/releases/tag/v1.20.1), [installation](https://qdrant.tech/documentation/operations/installation/) | Real application adapter6/6 checks passed; complete Compose run remains blocked |
| Nextcloud | `nextcloud:33.0.11-apache` | AGPL-3.0 | [Server release](https://github.com/nextcloud/server/releases/tag/v33.0.11), [community image](https://github.com/nextcloud/docker) | Image extraction blocked by ENOSPC; source-backed integration not tested |

Exact tags constrain versions but are not immutable digest pins. The observed
OpenFGA multiarchitecture manifest digest was
`sha256:b852071314f1fda1194d341a6ebac0a4f619b3cd87a6626d2ccc7048af4ec671`.
Rebuild on a different date may select changed base layers. This record is not
a dependency vulnerability scan or a statement that every upstream version is
free of vulnerabilities. See the run evidence for final execution status.

## Setup contract

From repository root, after installing the Python dependencies:

```bash
python scripts/bootstrap_live.py prepare
docker compose --env-file .env -f infra/compose/compose.yaml --profile core config --quiet
docker compose --env-file .env -f infra/compose/compose.yaml --profile core up -d postgres keycloak openfga qdrant
python scripts/bootstrap_live.py configure
docker compose --env-file .env -f infra/compose/compose.yaml --profile core up -d --build api
```

After API startup run `python scripts/bootstrap_live.py index` to obtain
separate tenant workload credentials and index through authenticated ingestion
endpoints. This command is implemented but full execution requires the
PostgreSQL-backed core, which could not run in the assessment environment.

`configure` creates and persists an OpenFGA store/model, then seeds initial
synthetic tuples only once. Subsequent runs preserve intentional permission
changes. It does not silently repair or reset user-created grants. If setup
fails mid-seed, rerun it; existing tuples are recognized. If the lab is
explicitly reset by deleting its own volumes, remove the generated `.env`
store/model/seed values or run the documented project reset command before
preparing again. Never use a global Docker prune.

The initial app database migration/fixture seed belongs to `p091.seed`, not to
OpenFGA bootstrap. App authorization mutations must update the SQL policy and
OpenFGA; the app denies content when either disagrees or is unavailable.

Each database has a separate owner and randomly generated 192-bit password.
The PostgreSQL bootstrap superuser is not given to the application. `.env` contains generated local secrets and must remain ignored by source
control and excluded from published archives.
The committed `infra/keycloak/p091-realm.json` contains only environment variable
placeholders and is readable by the non-root Keycloak container. Its import
substitution is documented by [Keycloak](https://www.keycloak.org/server/importExport).
Database initialization scripts run only when the project volume is empty.
Local metadata/fga/schema owners can run migrations; production would separate
migration and runtime privileges further.

## Identity and sessions

Six human identities have fixed synthetic IDs `nw-employee`, `nw-manager`,
`nw-admin`, `co-employee`, `co-manager`, `co-admin`. Their password is generated
in the local `.env` key `LAB_USER_PASSWORD`. Service clients `indexer` and
`contoso-indexer` use separate generated secrets and tenant-bound
`nw-indexer`/`co-indexer` service subjects.

The public `p091-web` client uses authorization code with PKCE S256 and exact
localhost redirect URIs; implicit/password/direct grant flows are disabled.
It receives the `read` scope. Optional `admin` is role-scoped to human tenant
admins. Request `openid read admin` in the browser; the app still independently
checks the stored tenant administrator role. Service clients receive only
`ingest`, no browser/read privileges. Human token group claims do not define
current app group membership.

The issuer remains browser-visible `http://localhost:8081/realms/p091`; the
backend fetches JWKS using internal service DNS. There is no algorithm or
issuer fallback. Stateless access-token expiry is 300 seconds. Application
logout invalidation and external Keycloak session revocation limitations must
be evaluated separately. A fresh JWKS request detects Keycloak availability,
not whether an individual previously issued JWT has been revoked.

## Extended Nextcloud source

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile extended up -d nextcloud
python scripts/seed_nextcloud.py
```

The seed creates synthetic human accounts, tenant/department groups,
connector-owned UTF-8 documents and OCS user/group shares. It writes harmless
source IDs/ETags to `work/nextcloud-versions.json`. Set
`NEXTCLOUD_ENABLED=true`, recreate the API, then run
`python scripts/bootstrap_live.py index` to bind source ETags through the
authenticated service ingestion workflow. Reads fail closed until the source
version and indexed version match.
The seeder is an explicit destructive seed for source contents: repeated runs
replace fixture bodies in this disposable Nextcloud. Do not run it against a
source corpus whose edits must be retained.

Nextcloud is the content store. App-controlled policy plus OpenFGA is the
assistant ACL authority. The connector's `oc:permissions` is that connector's
own effective access, not a complete graph of every user's inherited source
permission. This implementation does not claim generic ACL inheritance sync,
Groupfolders ACL support, federated/public shares, or bidirectional updates
from arbitrary source UI share changes. Nextcloud read/version failures must
deny content; exact propagation behavior is recorded only after testing.

References: [WebDAV properties and effective permissions](https://docs.nextcloud.com/server/33/developer_manual/client_apis/WebDAV/basic.html),
[OCS Share API](https://docs.nextcloud.com/server/33/developer_manual/client_apis/OCS/ocs-share-api.html),
[Provisioning API](https://docs.nextcloud.com/server/33/admin_manual/configuration_user/instruction_set_for_users.html).

## Health and teardown

PostgreSQL uses `pg_isready`. Keycloak uses the documented management-ready
endpoint via Bash TCP, since its image omits curl. OpenFGA uses its packaged
gRPC health probe. Qdrant health checks `/readyz` with the API key via Bash TCP;
a short-lived Python companion independently gates application startup.
Nextcloud checks its installed status using packaged PHP. API checks its
readiness route. A healthy container is not proof of an end-to-end security
control; consult the regression and live integration evidence.

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile extended down
```

Add `--volumes` only for an explicitly intended reset of this project's own
disposable storage. No service uses host networking, Docker socket mounts,
privileged mode or external published targets. Onyx, Langfuse and external
LLM providers are not included in this topology and are not claimed as tested
integrations.


## Observed execution limits and component reproduction

The assessment environment had an approximately 7.9 GiB filesystem and rootless
Docker using `vfs`. Core PostgreSQL and extended Nextcloud image extraction both
failed with `no space left on device`. A smaller PostgreSQL Alpine alternative
also failed; the committed topology remains on the original Bookworm pin.
These are setup blockers, not vulnerabilities or failed authorization controls.
Sanitized observations are retained in
[`infrastructure-blockers.json`](../docs/evidence/infrastructure-blockers.json).
No complete PostgreSQL-backed Compose or Nextcloud-backed run is claimed.
The group and department graph is modeled, but initial document viewer tuples
are flattened from the application effective policy. This is not evidence of
Nextcloud ACL inheritance synchronization.

The exact Keycloak realm and actual application verifier were still exercised
against a standalone real Keycloak container with H2. Component probes are
reproducible separately on a machine with Docker:

```bash
python scripts/bootstrap_live.py prepare
python infra/prepare_probe_env.py
docker run --rm -d --name p091-keycloak-probe --env-file work/keycloak-probe.env -p 127.0.0.1:8081:8080 -v "$PWD/infra/keycloak/p091-realm.json:/opt/keycloak/data/import/p091-realm.json:ro" quay.io/keycloak/keycloak:26.8.2 start-dev --import-realm --hostname=http://localhost:8081
# Wait for /realms/p091/.well-known/openid-configuration to return200.
.venv/bin/python infra/probe_keycloak.py
docker stop p091-keycloak-probe
docker run --rm -d --name p091-qdrant-probe --env-file work/qdrant-probe.env -p 127.0.0.1:6333:6333 -v "$PWD/infra/qdrant/healthcheck.sh:/healthcheck.sh:ro" qdrant/qdrant:v1.20.1
# Wait for the real readiness probe to succeed.
docker exec p091-qdrant-probe bash /healthcheck.sh
.venv/bin/python infra/probe_qdrant.py
docker stop p091-qdrant-probe
```

The probe ports conflict with a running Compose lab; stop the project first or
use a separate machine. Each probe has its own explicit container name and
`--rm`; no unrelated Docker objects are modified. The component scripts write
sanitized evidence and never save access tokens. Their positive results do not
establish a full assistant deployment, PostgreSQL compatibility, arbitrary
source ACL inheritance, or resilience to every outage.


The first real human PKCE token lacked `sub` because the custom client did not
include Keycloak's `basic` subject mapper. The API correctly denied the token;
this was an availability/integration defect with no observed unauthorized
content disclosure. The committed realm now explicitly includes the official
`oidc-sub-mapper`, as specified by the
[protocol mapper API](https://www.keycloak.org/admin-api/protocol-mappers) and
[Keycloak26.8.2 source](https://github.com/keycloak/keycloak/blob/26.8.2/services/src/main/java/org/keycloak/protocol/oidc/mappers/SubMapper.java).
Fresh human PKCE and service grant retest results are retained separately in the
evidence directory. Service accounts always included a subject, so their first
passing probes did not establish that human browser flows worked.
