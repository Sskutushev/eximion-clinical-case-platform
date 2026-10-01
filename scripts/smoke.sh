#!/usr/bin/env bash
# End-to-end smoke test of the vertical slice against a running stack.
#   create case -> read it back -> verify the answer key does not leak -> score -> verify persistence
set -euo pipefail

API="${API_BASE_URL:-http://localhost:8000}"
WEB="${WEB_BASE_URL:-http://localhost:3000}"
ADMIN_KEY="${ADMIN_API_KEY:-local-dev-admin-key}"

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }
ok() { echo "  ok  $*"; }

echo "1. health"
curl -fsS "${API}/health" | grep -q '"ok"' || fail "liveness"
curl -fsS "${API}/health/ready" | grep -q '"ok"' || fail "readiness (database)"
ok "api is live and the database is reachable"

echo "2. authoring requires the admin key"
status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API}/api/v1/cases" \
  -H 'Content-Type: application/json' --data '{}')
[ "${status}" = "401" ] || fail "unauthenticated authoring returned ${status}, expected 401"
ok "POST /cases rejects requests without the admin key"

echo "3. create a case"
created=$(curl -fsS -X POST "${API}/api/v1/cases" \
  -H 'Content-Type: application/json' -H "X-Admin-API-Key: ${ADMIN_KEY}" \
  --data '{
    "title": "Smoke test case",
    "patient_age": 24,
    "patient_sex": "male",
    "presentation": "Migratory abdominal pain for 18 hours with nausea.",
    "findings": [
      {"category": "symptom", "value": "Pain migrating to the right lower quadrant"},
      {"category": "laboratory", "value": "White cell count 14.2 x10^9/L"}
    ],
    "answers": [
      {"text": "Acute appendicitis", "is_correct": true, "score_weight": 10},
      {"text": "Mesenteric lymphadenitis", "is_correct": false, "score_weight": 3}
    ]
  }')
case_id=$(printf '%s' "${created}" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -n "${case_id}" ] || fail "no case id in response: ${created}"
ok "created case ${case_id}"

echo "4. the public read must not leak the answer key"
public=$(curl -fsS "${API}/api/v1/cases/${case_id}")
for leaked in appendicitis lymphadenitis is_correct score_weight answers; do
  if printf '%s' "${public}" | tr '[:upper:]' '[:lower:]' | grep -q "${leaked}"; then
    fail "public case exposes '${leaked}'"
  fi
done
printf '%s' "${public}" | grep -q 'right lower quadrant' || fail "findings missing from public case"
ok "answer key is not reachable through GET /cases/{id}"

echo "5. scoring"
correct=$(curl -fsS -X POST "${API}/api/v1/cases/${case_id}/score" \
  -H 'Content-Type: application/json' --data '{"answer": "  ACUTE   Appendicitis. "}')
printf '%s' "${correct}" | grep -q '"score":10' || fail "normalized correct answer not scored 10: ${correct}"
printf '%s' "${correct}" | grep -q '"outcome":"correct"' || fail "outcome not correct: ${correct}"
ok "normalized correct answer scores 10/10"

partial=$(curl -fsS -X POST "${API}/api/v1/cases/${case_id}/score" \
  -H 'Content-Type: application/json' --data '{"answer": "Mesenteric lymphadenitis"}')
printf '%s' "${partial}" | grep -q '"outcome":"partially_correct"' || fail "partial credit: ${partial}"
ok "differential answer scores partial credit"

wrong=$(curl -fsS -X POST "${API}/api/v1/cases/${case_id}/score" \
  -H 'Content-Type: application/json' --data '{"answer": "Migraine"}')
printf '%s' "${wrong}" | grep -q '"score":0' || fail "wrong answer not scored 0: ${wrong}"
ok "incorrect answer scores 0"

echo "6. unknown case and invalid input"
status=$(curl -s -o /dev/null -w '%{http_code}' \
  "${API}/api/v1/cases/00000000-0000-4000-8000-000000000000")
[ "${status}" = "404" ] || fail "unknown case returned ${status}, expected 404"
status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API}/api/v1/cases/${case_id}/score" \
  -H 'Content-Type: application/json' --data '{"answer": "   "}')
[ "${status}" = "422" ] || fail "blank answer returned ${status}, expected 422"
ok "error paths behave"

echo "7. frontend renders the case server-side"
if curl -fsS -o /dev/null "${WEB}" 2>/dev/null; then
  page=$(curl -fsS "${WEB}/cases/${case_id}")
  printf '%s' "${page}" | grep -q 'Smoke test case' || fail "case title missing from rendered page"
  printf '%s' "${page}" | grep -q 'Your diagnosis' || fail "diagnosis form missing from rendered page"
  if printf '%s' "${page}" | tr '[:upper:]' '[:lower:]' | grep -q 'appendicitis'; then
    fail "rendered page contains the answer key"
  fi
  ok "page renders the case and the form without leaking the answer key"
else
  echo "  skip  frontend not running at ${WEB}"
fi

echo
echo "SMOKE PASS"
