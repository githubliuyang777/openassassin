#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
FRONTEND="${FRONTEND_URL:-http://localhost:8080}"
PASS=0
FAIL=0

check() {
  local desc="$1" expected="$2" method="${3:-GET}" url="$4" data="${5:-}"
  local status
  status=$(curl -s -o /tmp/smoke_resp.txt -w "%{http_code}" -X "$method" "$url" \
    ${data:+-H 'Content-Type: application/json' -d "$data"})
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

# 3. List scripts (authenticated)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  check "GET /api/v1/scripts — authenticated" 200 GET "$BASE/api/v1/scripts" ""
  AUTH_HEADER="-H 'Authorization: Bearer $TOKEN'"
else
  echo "  SKIP authenticated tests (no token)"
fi

# 4. Create script
SCRIPT_ID=""
if [ -n "${TOKEN:-}" ] && [ "$TOKEN" != "null" ]; then
  status=$(curl -s -o /tmp/smoke_script.txt -w "%{http_code}" \
    -X POST "$BASE/api/v1/scripts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"smoke-test","type":"shell","content":"echo ok","timeout":30}')
  if [ "$status" = "200" ] || [ "$status" = "201" ]; then
    echo "  PASS POST /api/v1/scripts (HTTP $status)"
    PASS=$((PASS + 1))
    SCRIPT_ID=$(jq -r '.id' /tmp/smoke_script.txt 2>/dev/null || true)
  else
    echo "  FAIL POST /api/v1/scripts — expected 200/201, got $status"
    FAIL=$((FAIL + 1))
  fi
fi

# 5. List credentials
if [ -n "${TOKEN:-}" ] && [ "$TOKEN" != "null" ]; then
  check "GET /api/v1/credentials — authenticated" 200 GET "$BASE/api/v1/credentials" ""
fi

# 6. Frontend
check "Frontend :8080" 200 GET "$FRONTEND"

# 7. Unauthenticated access
check "GET /api/v1/scripts — unauthenticated" 401 GET "$BASE/api/v1/scripts"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
