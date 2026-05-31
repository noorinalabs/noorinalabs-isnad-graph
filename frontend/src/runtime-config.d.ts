// Runtime config injected by the container entrypoint via /runtime-config.js
// (envsubst over runtime-config.js.template). Loaded as the first <script> in
// index.html so `window.RUNTIME_CONFIG` is populated before any module code
// runs. Absent in local `npm run dev` (no entrypoint) — readers fall back to
// `import.meta.env.VITE_USER_SERVICE_ORIGIN`. See isnad-graph#932.
interface RuntimeConfig {
  USER_SERVICE_ORIGIN?: string
}

interface Window {
  RUNTIME_CONFIG?: RuntimeConfig
}
