/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Origin of the user-service vhost (`users.{base}`). Set per-environment
  // via `frontend/.env*` files. Empty/undefined falls back to same-origin —
  // see deploy#245 phase 2 for the carve-out context.
  readonly VITE_USER_SERVICE_ORIGIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
