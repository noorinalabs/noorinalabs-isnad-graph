#!/bin/sh
# Container entrypoint: render runtime-config.js from its committed template
# before starting nginx. envsubst (from the gettext package, installed in the
# final Dockerfile stage) substitutes only the variables we name explicitly so
# stray `$`-sequences elsewhere are left untouched.
#
# USER_SERVICE_ORIGIN is supplied by the compose `environment:` block
# (noorinalabs-deploy, templated per env via write-deploy-env). When unset it
# substitutes to the empty string, preserving the same-origin fallback that the
# transitional dual-bind relied on. See isnad-graph#932 / deploy#245 step 5.
set -eu

TEMPLATE=/runtime-config.js.template
OUTPUT=/usr/share/nginx/html/runtime-config.js

# The single-quoted SHELL-FORMAT argument is deliberate: it is an envsubst
# allowlist, not a shell expansion. Only ${USER_SERVICE_ORIGIN} is substituted;
# every other `$`-sequence in the template is left verbatim. shellcheck SC2016
# would have us double-quote it, which would break the intended behaviour.
# shellcheck disable=SC2016
envsubst '${USER_SERVICE_ORIGIN}' < "$TEMPLATE" > "$OUTPUT"

exec "$@"
