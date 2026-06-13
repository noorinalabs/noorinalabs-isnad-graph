#!/bin/sh
# Container entrypoint: render runtime-config.js from its committed template
# before starting nginx. envsubst (from the gettext package, installed in the
# final Dockerfile stage) substitutes only the variables we name explicitly so
# stray `$`-sequences elsewhere are left untouched.
#
# USER_SERVICE_ORIGIN and INGEST_PLATFORM_ORIGIN are supplied by the compose
# `environment:` block (noorinalabs-deploy, templated per env via
# write-deploy-env). When unset they substitute to the empty string.
# See isnad-graph#932 / deploy#245 step 5.
set -eu

TEMPLATE=/runtime-config.js.template
# Render to /tmp, not the html root: the deploy compose runs this container with
# `read_only: true` and only /tmp, /var/cache/nginx, /run are tmpfs (writable).
# Writing under /usr/share/nginx/html (the read-only rootfs) crash-loops the
# container at start (ig#949). nginx serves this path back at the original
# /runtime-config.js URL via an `alias` in nginx.conf, so index.html's
# `<script src="/runtime-config.js">` is unchanged.
OUTPUT=/tmp/runtime-config.js

# The single-quoted SHELL-FORMAT argument is deliberate: it is an envsubst
# allowlist, not a shell expansion. Only the listed variables are substituted;
# every other `$`-sequence in the template is left verbatim. shellcheck SC2016
# would have us double-quote it, which would break the intended behaviour.
# shellcheck disable=SC2016
envsubst '${USER_SERVICE_ORIGIN}${INGEST_PLATFORM_ORIGIN}' < "$TEMPLATE" > "$OUTPUT"

# Fail fast if any ${…} placeholder survived substitution unchanged. A residual
# placeholder means a variable was not listed in the allowlist above (or the
# compose environment block is missing a binding). Shipping silently would serve
# a malformed runtime-config to every client. See ig#1008.
if grep -qF '${' "$OUTPUT"; then
    printf 'entrypoint: ERROR: unsubstituted variable(s) remain in %s -- add missing var to envsubst allowlist\n' "$OUTPUT" >&2
    exit 1
fi

exec "$@"
