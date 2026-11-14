# Independent assessment challenge

**Human verification status: PENDING — UNATTEMPTED.** Generated implementation and passing automated tests do not establish the user's competence. An independent reviewer must observe the exercise and sign the rubric only after it is performed. Do not prefill a passing score.

## Conditions

Use a fresh disposable checkout and synthetic data only. First read the README, scope, architecture and retained results. Then close generated conclusions and work without coding-assistant help. Official documentation is allowed; record any human assistance. A reviewer chooses one source, one permitted user and one denied user without telling the candidate which boundary will fail. Allocate 90–120 minutes; the time target is advisory, not a pass criterion.

## Practical exercise

1. Bootstrap the documented offline lab, identify its tested dependencies and explain which optional services are simulated, mocked or actually live. Record the exact command and source digest/revision. Show one positive authorized query with a source-verifiable quotation.
2. Draw the flow for that query and identify the originating identity, tenant, policy source of truth, retrieved candidate, content store and outward representations. Explain why the indexer's visibility cannot authorize a human request.
3. Reproduce a controlled denial with a minimal request. Test direct ID, search, chat, citation, preview, history, summary and export paths that exist. Show the response status and prove that the forbidden marker **and title** did not escape. Do not infer absent leakage from status alone.
4. Ask an administrator to share a synthetic private document, read it, create an answer, remove the share and retry every applicable current and historical view. Repeat with group removal or deletion. Measure the last permitted and first denied operation and state what the measurement cannot establish about concurrent requests.
5. In an isolated **test-only** vulnerable fixture, bypass one authorization gate chosen by the reviewer. Demonstrate the resulting marker disclosure. Never enable a vulnerable route in the default application. Explain the failed trust boundary and business impact without calling the fixture a discovered product vulnerability.
6. Repair the fixture or missing gate, add one positive and one meaningful negative regression, rerun the minimum affected suite, and produce before/fix/after sanitized evidence. Show that the fix prevents the original reproduction while preserving normal access.
7. Plant instruction-like content in a source the employee may read. Attempt to make it reveal a Finance-only marker. Explain the observed extractive behavior and why it does not establish real-model immunity. Demonstrate that metadata/ranking cannot grant authority.
8. Present a three-minute client explanation covering verified behavior, remaining source-ACL and multi-process limits, remediation priority and the next reproducible command.

## Alternate architecture / policy variation

Replace permissive group inheritance with an explicit intersection policy: a user must belong to the document's tenant **and** department, and any document-specific deny overrides administrator or group grants. Propose an OpenFGA model or an equivalent external policy decision point; explain which relationships are authoritative and how a revocation becomes visible on each read. Do not edit the primary lab policy without preserving a runnable baseline.

Implement the variation in a separate branch/directory or pure policy test module. Supply a truth table covering employee, manager, tenant administrator, foreign tenant, explicit deny, deleted source and policy outage. Explain a safe migration from old tuples, how unknown state fails closed and why changing only vector tags is insufficient. A design sketch without executable positive/negative examples earns only partial credit.

## Objective reviewer rubric

| Gate | Required observable evidence | Score | Status |
| --- | --- | --- | --- |
| Reproduction | Fresh setup and source-verifiable allowed result | 0–2 | PENDING |
| Boundary explanation | Correct origin identity, policy authority and untrusted candidate/data distinction | 0–2 | PENDING |
| Attack proof | Minimal local request and actual synthetic disclosure in isolated fixture | 0–2 | PENDING |
| Fix | Root-cause correction plus useful authorized behavior | 0–2 | PENDING |
| Retest | Original request denied; additional read paths and stale views checked | 0–2 | PENDING |
| Evidence | Commands, IDs, versions, sanitized artifacts and limitations | 0–2 | PENDING |
| Policy variation | Executable truth table and safe revocation/migration reasoning | 0–2 | PENDING |
| Communication | Clear impact, measured claim and prioritized residual work | 0–2 | PENDING |

Scoring: 0 = absent/incorrect, 1 = partial or materially assisted, 2 = independently demonstrated. Suggested competency gate: at least 13/16 with a score of 2 on boundary explanation, attack proof, fix and retest. Any use of real data/unauthorized targets or fabricated evidence fails the exercise regardless of score. Record reviewer, date, source revision, evidence IDs, assistance and remaining gaps; no result is recorded yet.

## Oral-defense questions

1. What stops a forged vector candidate from revealing a forbidden title before document content is checked?
2. Why can a valid JWT with the correct tenant still be insufficient for access?
3. How do you distinguish a provider logout, JWT expiration, application logout and group revocation?
4. What exactly is authoritative when Nextcloud and the app disagree? Which external changes are currently unsupported?
5. Which behavior would you observe during an OpenFGA outage, and how would you prove the application did not silently fall back?
6. How could a correctly authorized current search coexist with a vulnerable historical-answer endpoint?
7. Which test proves citation grounding, and what does that proof say about source factual accuracy?
8. What guarantee does a single-process lock provide? What changes when two replicas serve requests?
9. Why is a vulnerable demonstration fixture not a confirmed vulnerability in the default application?
10. Which conclusions would need to be reevaluated when replacing extraction with a real model or enabling trace export?

## Feedback record

After the exercise, record misunderstood boundaries, irreproducible commands, false positives, lost utility and policy mismatches. Convert each confirmed lesson into a regression test or a documented assumption. Revisit this challenge after changes to identity, connector ACL fidelity, policy models, dependencies or generation adapters.
