FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# package-lock.json references @noorinalabs/design-system via a file: path
# pointing at /noorinalabs-design-system-0.0.1.tgz. The deploy script stages
# this tarball into the build context root before docker build (see #818).
# Long-term: switch to GHCR-published image (#817) or npm registry
# (design-system#57) and drop this implicit-contract copy.
COPY noorinalabs-design-system-0.0.1.tgz /
RUN npm ci
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
FROM nginx:stable-alpine3.23@sha256:0272e4604ed93c1792f03695a033a6e8546840f86e0de20a884bb17d2c924883
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
