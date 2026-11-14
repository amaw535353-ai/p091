# Control and test traceability

The machine-readable [CSV](control-and-test-traceability.csv) contains the requested engagement, risk, supporting project, tool, architecture boundary, abuse case, control, preconditions, authorized/denied expectation, test/evidence identity, observed status, remediation, retest, limitation and competency columns. Rebuild it with `.venv/bin/python scripts/build_traceability.py` after retaining actual test manifests.

Final coverage is **221 case/attempt/planned rows: 202 PASS, 0 FAIL, 3 INCONCLUSIVE, 13 NOT_TESTED, 3 NOT_APPLICABLE**. PASS denotes a defined assertion observed in its stated environment. It is not a finding count or blanket requirement certification. Infrastructure attempts that could not execute are inconclusive; absent live/optional/human proof stays not tested. Historical pre-remediation failures remain in finding evidence instead of being counted again in final regression status.

Mapped identifiers were verified against official sources in [standards references](standards-references.md). Related controls can be partially applicable. ATLAS labels identify threats, not assurance controls. NIST AI RMF GOVERN/MAP/MEASURE/MANAGE references describe lifecycle activities. Every human competency cell remains PENDING.

The final matrix deliberately separates the custom/offline policy from real Keycloak/OpenFGA/Qdrant component tests and unverified Nextcloud/PostgreSQL acceptance. No custom implementation result is attributed to Onyx, Langfuse or a stochastic model.
