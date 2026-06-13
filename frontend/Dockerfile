FROM node:24-alpine AS build
WORKDIR /app
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
# bump (or alpine 3.24+ when nginx publishes it).
FROM nginx:stable-alpine3.23@sha256:5f979dcfed4ce6461873f087e8c980d6e29b084b9e8776d9704a7e989b5f4898
# gettext provides `envsubst`, used by entrypoint.sh to render runtime-config.js
# from its template at container start (isnad-graph#932).
RUN apk upgrade --no-cache && apk add --no-cache gettext
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
