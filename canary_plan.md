**Version bump: v2 → v4** (v3 failed its suite run and was never released; recorded in `prompt_release.json`).

**Canary:** v4 serves 10% of users, chosen by a stable hash of `user_id` (`prompts.version_for`), for 48 hours or 200 canary requests, whichever comes later. Promote to production only if `dairy_free_swap_is_safe` and `cited_chunks_exist` fail on 0 canary log lines, and v4's refusal rate stays within 10 points of v2's.
**Rollback:** set `"canary_percent": 0` in `prompt_release.json`; no deploy, takes effect on the next request. If v2 itself must come out, set `"production": "v1"`, the last version with no recorded dairy-free failure, and rerun `run_suite.py` against it before closing the incident.
