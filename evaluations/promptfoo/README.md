# Local repeatable evaluation

This suite uses **Promptfoo 0.125.1** (MIT), pinned in `package-lock.json`.
The official npm registry reports Node `>=22.22.0`; the observed host is Node
24.22.1. Run from the repository root:

```sh
python scripts/run_promptfoo.py
```

The runner starts an isolated offline API on a loopback ephemeral port, runs the
local custom provider, writes sanitized results under `docs/evidence/promptfoo/`,
and stops its API. Alternatively, point `P091_BASE_URL` at your existing owned
offline lab and run `npm run eval` from this directory. The provider refuses
non-loopback and non-HTTP targets; it does not accept a remote model target.

Install dependencies with `npm ci` here first (the runner does this if needed).
Set an explicit writable npm cache if the host's home directory is unavailable:
`npm --cache /workspace/work/npm-cache ci`. Installing dependencies uses the npm
registry; running evaluations uses only localhost. Promptfoo telemetry is
disabled by the runner and no model API key or paid evaluator is used.

These are deterministic API regression cases, **not** model jailbreak results.
No stochastic model, sampling distribution, or universal immunity is claimed.
`EVAL-005` requires the seeded injection marker and a citation quote containing
the attack instruction. It also checks that an inaccessible Finance canary did
not cross the authorization boundary. The Python boundary suite exercises
additional document, source-version, and permission-change paths.
The report must distinguish assertions satisfied by empty retrieval from the
positive utility checks that require citations.

Official references checked 2026-11-14:

- [JavaScript custom-provider interface](https://www.promptfoo.dev/docs/providers/custom-api/)
- [Configuration reference](https://www.promptfoo.dev/docs/configuration/reference/)
- [Package registry metadata](https://registry.npmjs.org/promptfoo/0.125.1)

No results are asserted in this README. Inspect the retained manifest and result
JSON after running the command.
