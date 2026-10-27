#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
FRONTEND="${FRONTEND_URL:-http://localhost:8080}"
PASS=0
FAIL=0

check() {
  local desc="$1" expected="$2" method="${3:-GET}" url="$4" data="${5:-}" headers="${6:-}"
  local status
  status=$(curl -s -o /tmp/smoke_resp.txt -w "%{http_code}" -X "$method" "$url" \
    ${data:+-H 'Content-Type: application/json' -d "$data"} \
    ${headers:+-H "$headers"})
  if [ "$status" = "$expected" ]; then
    echo "  PASS $desc (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL $desc — expected $expected, got $status"
    cat /tmp/smoke_resp.txt 2>/dev/null || true
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Smoke tests ==="
echo ""

# 1. Login
check "POST /api/v1/auth/login — valid credentials" 200 POST "$BASE/api/v1/auth/login" \
  '{"username":"admin","password":"admin"}'
TOKEN=$(jq -r '.access_token' /tmp/smoke_resp.txt 2>/dev/null || true)

# 2. Auth guard
check "POST /api/v1/auth/login — bad password" 401 POST "$BASE/api/v1/auth/login" \
  '{"username":"admin","password":"wrong"}'

AUTH_HEADER=""
if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  AUTH_HEADER="Authorization: Bearer $TOKEN"
else
  echo "  SKIP authenticated tests (no token obtained from login)"
fi

# 3. List scripts (authenticated)
if [ -n "$AUTH_HEADER" ]; then
  check "GET /api/v1/scripts — authenticated" 200 GET "$BASE/api/v1/scripts" "" "$AUTH_HEADER"
fi

# 4. Create script
if [ -n "$AUTH_HEADER" ]; then
  status=$(curl -s -o /tmp/smoke_script.txt -w "%{http_code}" \
    -X POST "$BASE/api/v1/scripts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"smoke-test","type":"shell","content":"echo ok","timeout":30}')
  if [ "$status" = "200" ] || [ "$status" = "201" ]; then
    echo "  PASS POST /api/v1/scripts (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL POST /api/v1/scripts — expected 200/201, got $status"
    cat /tmp/smoke_script.txt 2>/dev/null || true
    FAIL=$((FAIL + 1))
  fi
fi

# 5. List credentials
if [ -n "$AUTH_HEADER" ]; then
  check "GET /api/v1/credentials — authenticated" 200 GET "$BASE/api/v1/credentials" "" "$AUTH_HEADER"
fi

# 6. Website version (admin only)
if [ -n "$AUTH_HEADER" ]; then
  check "GET /api/v1/system/version — authenticated admin" 200 GET "$BASE/api/v1/system/version" "" "$AUTH_HEADER"
  APP_VERSION_VALUE=$(jq -r '.version // empty' /tmp/smoke_resp.txt 2>/dev/null || true)
  if [ -n "$APP_VERSION_VALUE" ] && [ "$APP_VERSION_VALUE" != "null" ]; then
    echo "  PASS website version is non-empty ($APP_VERSION_VALUE)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL website version is empty"
    FAIL=$((FAIL + 1))
  fi
  if [ -n "${EXPECTED_APP_VERSION:-}" ]; then
    if [ "$APP_VERSION_VALUE" = "$EXPECTED_APP_VERSION" ]; then
      echo "  PASS website version matches EXPECTED_APP_VERSION"
      PASS=$((PASS + 1))
    else
      echo "  FAIL website version — expected $EXPECTED_APP_VERSION, got $APP_VERSION_VALUE"
      FAIL=$((FAIL + 1))
    fi
  fi
fi

# 7. Frontend
check "Frontend :8080" 200 GET "$FRONTEND"

# 8. Unauthenticated access
check "GET /api/v1/scripts — unauthenticated" 403 GET "$BASE/api/v1/scripts"
check "GET /api/v1/system/version — unauthenticated" 403 GET "$BASE/api/v1/system/version"
check "GET /docs — disabled" 404 GET "$BASE/docs"
check "GET /openapi.json — disabled" 404 GET "$BASE/openapi.json"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
