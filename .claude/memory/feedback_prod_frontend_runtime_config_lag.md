---
name: feedback_prod_frontend_runtime_config_lag
description: "isnad-graph frontend resolves user-service origin via window.RUNTIME_CONFIG injected by /runtime-config.js at serve time; prod ran an OLDER image (no runtime-config.js + empty baked VITE_USER_SERVICE_ORIGIN) → auth fetch hit same-origin SPA HTML → login JSON.parse error. Prod frontend image/runtime-config can silently lag stg."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 080813cd-f3b8-434d-974c-badf58620c96
---

**Symptom (prod-only, 2026-06-11):** prod login (`isnad.noorinalabs.com`) → `JSON.parse: unexpected character at line 1 column 1`; stg login fine. Filed deploy#420 (W3, owner-gated prod deploy).

**RESOLVED 2026-06-12:** prod promoted to `prod-b52f46f` (api+frontend, digests api `5490173d…`/frontend `63e56414…`) and rolled out (owner-approved). Prod `GET /runtime-config.js` now → 200 `application/javascript` with `window.RUNTIME_CONFIG = { USER_SERVICE_ORIGIN: "https://users.noorinalabs.com" }`; index loads `<script src="/runtime-config.js">`; prod smoke 7/7 incl. the new anti-drift check #7 (PR #421). Login JSON.parse gone. The getting-there was a saga — promote gate bug ([[project_promote_gate_stg_verify_refresh]]: deploy#423/#425), trigger-prod-deploy skip (#427, had to dispatch deploy-prod.yml manually), and the rollout briefly took prod DOWN because `compose up` aborted on an unhealthy NON-app kafka (stray Bitnami `config`/`data` dirs in `noorinalabs_kafka_data`; #428) leaving caddy+frontend `Created` (#429) — restored with `docker compose up -d frontend caddy`.

**Mechanism — how the frontend resolves the user-service origin:** `LoginPage.tsx` / `useAuth.ts` build `AUTH_BASE = ${USER_SERVICE_ORIGIN}/auth` and `fetch(\`${AUTH_BASE}/providers\`).then(r => r.ok ? r.json() : …)`. `USER_SERVICE_ORIGIN` comes from `VITE_USER_SERVICE_ORIGIN` (build-time) OR, in the **newer** image, from `window.RUNTIME_CONFIG` injected at serve time by `<script src="/runtime-config.js">` in `index.html`. Caddy serves the SPA `index.html` (HTTP **200**, `text/html`) for any unrouted path, so `r.ok` is true and the code calls `r.json()` on HTML → the JSON.parse throw. `/auth/*` is NOT routed to user-service on the isnad subdomain on either env — the origin MUST point at the `users.<domain>` subdomain (returns JSON).

**Root cause:** prod was running an **older frontend image** that (a) baked `VITE_USER_SERVICE_ORIGIN=""` → `AUTH_BASE="/auth"` same-origin, AND (b) predated the runtime-config feature (no `<script src="/runtime-config.js">`; prod `GET /runtime-config.js` → 200 SPA-HTML, file absent). stg's image emits the script and reads `window.RUNTIME_CONFIG` → origin = `https://users.stg.noorinalabs.com`.

**How to verify prod vs stg fast (read-only, no deploy):**
- `curl -s https://isnad.<env>/ | grep runtime-config.js` — present on the good (stg) env, absent on the lagging one.
- `curl -s https://isnad.<env>/runtime-config.js` — should be a JS config script, NOT `<!DOCTYPE html>`.
- grep the shipped bundle (`/assets/index-*.js`) for the AUTH_BASE var: `Zu="/auth"` (origin baked empty, broken) vs `pf=\`${zL}/auth\`` where `zL` reads `window.RUNTIME_CONFIG` (runtime, correct).

**Why / how to apply:** prod frontend image + its `/runtime-config.js` can silently lag stg even when stg is green — same class as the per-service-tag-routing lag [[feedback_stg_deploy_per_service_tag_routing]]. Fix = promote prod to stg-parity image + ensure prod deploy injects `/runtime-config.js` with `userServiceOrigin=https://users.noorinalabs.com`. Harden: post-deploy smoke that `GET /runtime-config.js` returns a script (not text/html) per env; defensive content-type guard before `r.json()` in the login fetches; `VITE_USER_SERVICE_ORIGIN` has 4 sources of truth (deploy `env-inventory.md`) — consolidate on the runtime-config path. Prod deploy itself is owner-gated.
