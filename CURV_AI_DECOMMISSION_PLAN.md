# CURV AI — Decommission Plan

**Date:** 2026-10-06 · No deletions performed — classification + recommended actions only.

| Candidate | Imports | Deployed? | CI/workflow refs | Makefile/compose refs | Docs refs | Verdict | Action |
|---|---|---|---|---|---|---|---|
| `apps/web` (legacy, 117 files) | none from prod code; standalone app | **No** (web-v2 is deployed) | none (CI targets web-v2) | **Yes** — `make web`, install, lint, typecheck, clean; docker-compose `web` svc | AGENTS.md layout | **DEPRECATE** | 1) Retarget Makefile `web`→`apps/web-v2`; remove compose svc. 2) Move `apps/web`→`archive/apps-web/` or delete after 2-wk soak. Removes dev-only `braces` vuln + halves workspace surface. |
| `apps/api/routers/` | — | — | — | — | — | **SAFE TO REMOVE** | Empty dir. `rm -rf`. |
| `apps/workers/{ads,organic,ingest,measure,creative}` | — (real code in `prachar_workers/`) | — | — | — | — | **SAFE TO REMOVE** | Empty dirs. `rm -rf`. |
| `apps/ai-gen` (Modal svc) | **Nothing** — `ai_gen_url` config field unused; no API call site; never deployed; no CI ref | Never deployed | none | none | DEPLOY.md, modal_app.py docstring | **DEPRECATE** | Keep `ai_gen_url` field (harmless) or drop in next config cleanup. Move `apps/ai-gen`→`archive/`. fal.ai is the canonical video path. |
| `apps/api/prachar_api/infrastructure/_memory_repos.py` | test/dev DI repos | — | used by tests | — | — | **KEEP** | In-memory repos used by test fixtures — legitimate. |
| `apps/api/prachar_api/routers/__pycache__`+stale `.pyc` | — | — | — | — | — | **SAFE TO REMOVE** | Build artifacts in repo. |

## Notes

- `apps/web` removal kills the only remaining npm-audit finding (dev-only `braces`) and ~117 files of dead surface — but it is still wired as the Makefile's default `web` target, so it must be deprecated (pointer retarget) before deletion.
- `apps/ai-gen` is the only case where audit evidence clearly shows "built, never connected": the video path uses fal.ai REST directly; the Modal deployment URLs in `modal_app.py` comments were never reachable from the API.
