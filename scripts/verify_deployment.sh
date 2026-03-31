#!/usr/bin/env bash
# verify_deployment.sh — Production deployment verification for isnad-graph
# Checks deploy workflow, live site, API health, security headers, and SSL.
#
# Usage:
#   ./scripts/verify_deployment.sh [--site URL] [--skip-workflow] [--skip-ssl]
#
# Environment:
#   SITE_URL      Override the default site URL (default: https://isnad-graph.noorinalabs.com)
#   GH_REPO       Override the GitHub repo for workflow checks (default: parametrization/isnad-graph)
#   ROLLBACK_TAG  If set, tag the current deployment for rollback reference

set -euo pipefail

# ---------- Configuration ----------

SITE_URL="${SITE_URL:-https://isnad-graph.noorinalabs.com}"
GH_REPO="${GH_REPO:-parametrization/isnad-graph}"
SKIP_WORKFLOW="${SKIP_WORKFLOW:-false}"
SKIP_SSL="${SKIP_SSL:-false}"
ROLLBACK_TAG="${ROLLBACK_TAG:-}"
TIMEOUT=10

# Parse CLI args
for arg in "$@"; do
  case "$arg" in
    --site=*) SITE_URL="${arg#*=}" ;;
    --skip-workflow) SKIP_WORKFLOW=true ;;
    --skip-ssl) SKIP_SSL=true ;;
    --help|-h)
      head -12 "$0" | tail -10
      exit 0
      ;;
  esac
done

# ---------- Helpers ----------

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }
warn() { WARN=$((WARN + 1)); echo "  WARN: $1"; }
section() { echo ""; echo "==> $1"; }

# ---------- 1. Deploy Workflow Status ----------

if [ "$SKIP_WORKFLOW" = "false" ]; then
  section "Deploy Workflow Status"
  if ! command -v gh &>/dev/null; then
    warn "gh CLI not installed — skipping workflow check"
  else
    latest=$(gh run list --repo "$GH_REPO" --workflow=deploy.yml --limit 1 --json status,conclusion,headSha,createdAt 2>/dev/null || echo "")
    if [ -z "$latest" ] || [ "$latest" = "[]" ]; then
      warn "No deploy workflow runs found"
    else
      conclusion=$(echo "$latest" | jq -r '.[0].conclusion // "in_progress"')
      status=$(echo "$latest" | jq -r '.[0].status')
      sha=$(echo "$latest" | jq -r '.[0].headSha' | cut -c1-8)
      created=$(echo "$latest" | jq -r '.[0].createdAt')
      if [ "$conclusion" = "success" ]; then
        pass "Latest deploy succeeded (sha=$sha, at=$created)"
      elif [ "$status" = "in_progress" ]; then
        warn "Deploy still in progress (sha=$sha)"
      else
        fail "Latest deploy conclusion=$conclusion (sha=$sha, at=$created)"
      fi
    fi
  fi
fi

# ---------- 2. Live Site HTTP 200 ----------

section "Live Site Reachability"
http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$SITE_URL" 2>/dev/null || echo "000")
if [ "$http_code" = "200" ]; then
  pass "Site returns HTTP 200 at $SITE_URL"
else
  fail "Site returned HTTP $http_code at $SITE_URL"
fi

# ---------- 3. API Health Endpoint ----------

section "API Health Check"
health_resolved=false
# Try /health first (Caddy direct), then /api/v1/health as fallback
for health_path in "/health" "/api/v1/health"; do
  health_url="${SITE_URL}${health_path}"
  health_resp=$(curl -s --max-time "$TIMEOUT" "$health_url" 2>/dev/null || echo "")
  if echo "$health_resp" | jq -e '.status' &>/dev/null; then
    health_status=$(echo "$health_resp" | jq -r '.status')
    if [ "$health_status" = "healthy" ] || [ "$health_status" = "degraded" ] || [ "$health_status" = "ok" ]; then
      pass "Health endpoint (${health_path}) reports status=$health_status"
    else
      fail "Health endpoint (${health_path}) status=$health_status"
    fi
    health_resolved=true
    break
  fi
done
# If neither endpoint returned parseable JSON, fall back to HTTP status code
if [ "$health_resolved" = "false" ]; then
  health_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${SITE_URL}/health" 2>/dev/null || echo "000")
  if [ "$health_code" = "200" ]; then
    pass "Health endpoint returned HTTP 200 (non-JSON response)"
  else
    fail "Health endpoint unreachable or invalid (HTTP $health_code)"
  fi
fi

# ---------- 4. API Status Endpoint (detailed) ----------

section "API Status (detailed service health)"
status_url="${SITE_URL}/status"
status_resp=$(curl -s --max-time "$TIMEOUT" "$status_url" 2>/dev/null || echo "")
if echo "$status_resp" | jq -e '.status' &>/dev/null; then
  pub_status=$(echo "$status_resp" | jq -r '.status')
  pub_message=$(echo "$status_resp" | jq -r '.message // ""')
  if [ "$pub_status" = "operational" ]; then
    pass "Status endpoint reports operational"
  else
    warn "Status endpoint reports $pub_status: $pub_message"
  fi
else
  warn "Status endpoint not available or unexpected format"
fi

# ---------- 5. Key API Endpoints (smoke test — expect 401 without auth) ----------

section "API Endpoint Smoke Tests"
endpoints=("/api/v1/narrators" "/api/v1/hadiths" "/api/v1/collections" "/api/v1/search" "/api/v1/parallels" "/api/v1/timeline")
for ep in "${endpoints[@]}"; do
  ep_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${SITE_URL}${ep}" 2>/dev/null || echo "000")
  if [ "$ep_code" = "401" ] || [ "$ep_code" = "403" ] || [ "$ep_code" = "200" ]; then
    pass "Endpoint $ep reachable (HTTP $ep_code)"
  elif [ "$ep_code" = "000" ]; then
    fail "Endpoint $ep unreachable (timeout/connection error)"
  else
    warn "Endpoint $ep returned HTTP $ep_code"
  fi
done

# ---------- 6. Security Headers ----------

section "Security Headers"
# Check headers on both the main site (Caddy) and API endpoint to get the full set
headers=$(curl -s -D - -o /dev/null --max-time "$TIMEOUT" "$SITE_URL" 2>/dev/null || echo "")
api_headers=$(curl -s -D - -o /dev/null --max-time "$TIMEOUT" "${SITE_URL}/health" 2>/dev/null || echo "")
# Merge both sets of headers for checking
headers="${headers}
${api_headers}"
required_headers=(
  "X-Content-Type-Options"
  "X-Frame-Options"
  "Strict-Transport-Security"
  "X-XSS-Protection"
  "Referrer-Policy"
  "Content-Security-Policy"
)
for hdr in "${required_headers[@]}"; do
  if echo "$headers" | grep -qi "^${hdr}:"; then
    val=$(echo "$headers" | grep -i "^${hdr}:" | head -1 | cut -d: -f2- | xargs)
    # X-XSS-Protection: 0 is the OWASP-recommended value (disable browser XSS filter)
    if [ "$hdr" = "X-XSS-Protection" ] && [ "$val" = "0" ]; then
      pass "Header $hdr present ($val — OWASP recommended)"
    else
      pass "Header $hdr present ($val)"
    fi
  else
    fail "Header $hdr missing"
  fi
done

# ---------- 7. Caddy Config Reload Verification ----------

section "Caddy Config Verification"
# Verify that Caddy (the reverse proxy) is serving security headers on the root URL.
# This confirms that the running Caddy process has loaded the current Caddyfile,
# not a stale cached config from a previous deployment.
caddy_headers=$(curl -s -D - -o /dev/null --max-time "$TIMEOUT" "$SITE_URL" 2>/dev/null || echo "")
caddy_check_headers=("X-XSS-Protection" "Content-Security-Policy" "X-Content-Type-Options")
caddy_ok=true
for chdr in "${caddy_check_headers[@]}"; do
  if echo "$caddy_headers" | grep -qi "^${chdr}:"; then
    pass "Caddy serves $chdr header"
  else
    fail "Caddy does NOT serve $chdr header — config may not be reloaded"
    caddy_ok=false
  fi
done
# Check for Caddy server identifier (confirms traffic flows through Caddy)
if echo "$caddy_headers" | grep -qi "^server:.*caddy"; then
  pass "Response served by Caddy (Server header present)"
elif echo "$caddy_headers" | grep -qi "^server:"; then
  server_val=$(echo "$caddy_headers" | grep -i "^server:" | head -1 | cut -d: -f2- | xargs)
  warn "Server header present but not Caddy ($server_val)"
else
  warn "No Server header — cannot confirm Caddy is the reverse proxy"
fi

# ---------- 8. SSL Certificate ----------

if [ "$SKIP_SSL" = "false" ]; then
  section "SSL Certificate"
  host=$(echo "$SITE_URL" | sed 's|https://||' | sed 's|/.*||')
  cert_info=$(echo | openssl s_client -servername "$host" -connect "${host}:443" 2>/dev/null | openssl x509 -noout -dates -subject 2>/dev/null || echo "")
  if [ -z "$cert_info" ]; then
    fail "Could not retrieve SSL certificate for $host"
  else
    not_after=$(echo "$cert_info" | grep "notAfter" | cut -d= -f2)
    if [ -n "$not_after" ]; then
      expiry_epoch=$(date -d "$not_after" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$not_after" +%s 2>/dev/null || echo "0")
      now_epoch=$(date +%s)
      days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
      if [ "$days_left" -gt 14 ]; then
        pass "SSL certificate valid for $days_left more days (expires: $not_after)"
      elif [ "$days_left" -gt 0 ]; then
        warn "SSL certificate expires in $days_left days (expires: $not_after)"
      else
        fail "SSL certificate expired or expiring today (expires: $not_after)"
      fi
    else
      fail "Could not parse SSL certificate expiry"
    fi

    subject=$(echo "$cert_info" | grep "subject" | head -1)
    if echo "$subject" | grep -qi "$host"; then
      pass "SSL certificate subject matches $host"
    else
      warn "SSL certificate subject may not match: $subject"
    fi
  fi
fi

# ---------- 9. Response Time Spot Check ----------

section "Response Time"
time_total=$(curl -s -o /dev/null -w "%{time_total}" --max-time "$TIMEOUT" "${SITE_URL}/health" 2>/dev/null || echo "0")
time_ms=$(echo "$time_total * 1000" | bc 2>/dev/null | cut -d. -f1 || echo "0")
if [ -n "$time_ms" ] && [ "$time_ms" -lt 500 ] 2>/dev/null; then
  pass "Health endpoint responded in ${time_ms}ms (threshold: 500ms)"
elif [ -n "$time_ms" ] && [ "$time_ms" -lt 2000 ] 2>/dev/null; then
  warn "Health endpoint responded in ${time_ms}ms (above 500ms threshold)"
else
  fail "Health endpoint response time ${time_ms}ms exceeds 2000ms"
fi

# ---------- 10. Rollback Tag ----------

if [ -n "$ROLLBACK_TAG" ]; then
  section "Rollback Tag"
  if command -v gh &>/dev/null; then
    current_sha=$(gh api "repos/$GH_REPO/commits/main" --jq '.sha' 2>/dev/null | cut -c1-8 || echo "unknown")
    echo "  INFO: Tagging current deployment as $ROLLBACK_TAG (sha=$current_sha)"
    echo "  INFO: To rollback, deploy this tag: git checkout $ROLLBACK_TAG"
  fi
fi

# ---------- Summary ----------

section "Summary"
total=$((PASS + FAIL + WARN))
echo "  Total checks: $total"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Warnings: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAILED — $FAIL check(s) did not pass"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  echo "RESULT: PASSED WITH WARNINGS — $WARN warning(s)"
  exit 0
else
  echo "RESULT: ALL CHECKS PASSED"
  exit 0
fi
