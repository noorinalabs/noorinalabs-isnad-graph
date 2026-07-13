# Build stage pinned to node:24-alpine by digest for supply-chain reproducibility
# (charter tech-decisions.md § Base Image Pinning, isnad-graph#1142 / main#735).
# The digest is the multi-arch OCI index (amd64 + arm64). `apk upgrade --no-cache`
# pulls the latest alpine patches so the build toolchain isn't itself running
# known-fixed CVEs; the compiled dist/ is copied into the (separately pinned +
# upgraded) nginx runtime stage below. Re-pin to a newer digest on each node
# minor bump.
FROM node:24-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd AS build
WORKDIR /app
RUN apk upgrade --no-cache
# package-lock.json resolves @noorinalabs/design-system from GitHub Packages
# (npm.pkg.github.com) — see #940. .npmrc points the @noorinalabs scope at that
# registry and reads the token from ${NODE_AUTH_TOKEN}; the token is supplied to
# `npm ci` below via a BuildKit secret (never a build-arg/layer), so it is not
# baked into the image. Package is org-public but the registry still requires a
# read token, hence the secret. ghcr-publish.yml sources it from GITHUB_TOKEN
# (packages:read). Local builds: `--secret id=node_auth_token,env=NODE_AUTH_TOKEN`.
COPY package.json package-lock.json .npmrc ./
RUN --mount=type=secret,id=node_auth_token \
    NODE_AUTH_TOKEN="$(cat /run/secrets/node_auth_token)" npm ci
# Cache-bust: ARG changes invalidate all subsequent layers
ARG CACHEBUST=1
COPY . .
RUN npm run build

# Runtime base pinned to nginx:stable-alpine3.23 by digest for supply-chain
# reproducibility. `apk upgrade --no-cache` then pulls the latest alpine
# package patches at build time so we don't ship known-fixed CVEs (e.g.
# CVE-2026-27135 in nghttp2-libs, isnad-graph#853). The digest pin freezes
# the starting layer; the upgrade step keeps OS packages current within the
# alpine 3.23 patch lifecycle. Re-pin to a newer digest on each minor nginx
# bump (or alpine 3.24+ when nginx publishes it) — but note the `stable-alpine3.23`
# tag still resolves to this same digest, so a digest re-pin alone does NOT move
# OS-package versions; the CVE floor below is what clears the Trivy gate.
FROM nginx:stable-alpine3.23@sha256:0d3b80406a13a767339fbe2f41406d6c7da727ab89cf8fae399e81f780f814d1
# gettext provides `envsubst`, used by entrypoint.sh to render runtime-config.js
# from its template at container start (isnad-graph#932).
#
# Explicit CVE floor (isnad-graph#1186): `apk upgrade` alone is not sufficient
# here — the fixed c-ares/libexpat packages are published to the alpine 3.23
# repo but reach mirrors on a lag, so a plain `apk upgrade` intermittently
# leaves the pre-fix versions and the frontend Trivy scan fails on 4 HIGH CVEs
# (c-ares CVE-2026-33630; libexpat CVE-2026-56131/-56407/-56408). Pinning the
# fixed floors makes the requirement explicit and build-enforced: the build
# fails loudly if the fix ever becomes unreachable, instead of silently
# shipping the vulnerable version. Bump/drop these once alpine 3.23's default
# package set carries them unconditionally.
RUN apk upgrade --no-cache \
    && apk add --no-cache gettext "c-ares>=1.34.8-r0" "libexpat>=2.8.2-r0"
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Runtime-config injection: the entrypoint renders /runtime-config.js from the
# committed template (envsubst with USER_SERVICE_ORIGIN from the compose
# environment) before handing off to nginx. Lets one image digest target
# env-specific origins at runtime. See isnad-graph#932 / deploy#245 step 5.
COPY runtime-config.js.template /runtime-config.js.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
