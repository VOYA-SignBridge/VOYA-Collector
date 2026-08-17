#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FULL routing evidence for the /voya sub-path gateway fix.
#
# Runs the ACTUAL nginx.conf as the gateway, with two tiny nginx "echo"
# containers as the backend/frontend upstreams (each returns which upstream it
# is + the exact path it received). It then exercises EVERY location in
# nginx.conf, both at root and under /voya, and asserts:
#
#     response("/voya" + P)  ==  response(P)        (for every route P)
#
# i.e. the gateway strips /voya and routes identically to the root deploy.
# Plus two special cases: bare "/voya" -> 301, and the auth rate-limit still
# fires under /voya.
#
# DEV-ONLY tool — not shipped in any image (backend copies only app/, frontend
# ships only dist/). Requires Docker + Git Bash. Run from the repo:
#     & "C:\Program Files\Git\bin\bash.exe" scripts/test_nginx_voya.sh
# ---------------------------------------------------------------------------
set -u
export MSYS_NO_PATHCONV=1

# Repo root derived from this script's own location -> portable, no hardcoding.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_NIX="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_WIN="$(cd "$REPO_NIX" && pwd -W 2>/dev/null || echo "$REPO_NIX")"  # Windows form for docker -v
NGINX_CONF="$REPO_WIN/nginx.conf"
MOCK_DIR_WIN="$REPO_WIN/_tmp/nginxtest"
MOCK_DIR_NIX="$REPO_NIX/_tmp/nginxtest"
NET="voya_nginx_test"; GW="voya_test_gw"; BE="backend"; FE="frontend"; PORT="8088"

cleanup() { docker rm -f "$GW" "$BE" "$FE" >/dev/null 2>&1; docker network rm "$NET" >/dev/null 2>&1; }
trap cleanup EXIT
cleanup

mkdir -p "$MOCK_DIR_NIX"
cat > "$MOCK_DIR_NIX/be.conf" <<'EOF'
events {}
http { server { listen 8000; location / { default_type text/plain; return 200 "BACKEND  $request_uri"; } } }
EOF
cat > "$MOCK_DIR_NIX/fe.conf" <<'EOF'
events {}
http { server { listen 80; location / { default_type text/plain; return 200 "FRONTEND $request_uri"; } } }
EOF

echo "=> starting mock upstreams + gateway (REAL nginx.conf) ..."
docker network create "$NET" >/dev/null 2>&1
docker run -d --name "$BE" --network "$NET" --network-alias backend  -v "$MOCK_DIR_WIN/be.conf:/etc/nginx/nginx.conf:ro" nginx:alpine >/dev/null
docker run -d --name "$FE" --network "$NET" --network-alias frontend -v "$MOCK_DIR_WIN/fe.conf:/etc/nginx/nginx.conf:ro" nginx:alpine >/dev/null
docker run -d --name "$GW" --network "$NET" -p "$PORT:80" -v "$NGINX_CONF:/etc/nginx/nginx.conf:ro" nginx:alpine >/dev/null
for _ in $(seq 1 20); do curl -s "http://localhost:$PORT/" >/dev/null 2>&1 && break; sleep 0.5; done

# A UNIQUE X-Forwarded-For per call gives each routing check its own rate-limit
# bucket, so the global api_limit never interferes with routing assertions.
_xff() { echo "10.$((RANDOM % 256)).$((RANDOM % 256)).$((RANDOM % 256))"; }
hit()  { curl -s -H "X-Forwarded-For: $(_xff)" "http://localhost:$PORT$1"; }
code() { curl -s -o /dev/null -w '%{http_code}' -H "X-Forwarded-For: $(_xff)" "http://localhost:$PORT$1"; }

# Every distinct route class in nginx.conf (backend + frontend + edge cases).
ROUTES=(
  # --- backend: health / api / auth / catalog / realtime-api / upload ---
  "/health"
  "/health/live"
  "/api/v1/auth/login"
  "/api/v1/classes"
  "/api/v1/training/ws/job123"
  "/api/v1/auth/refresh?token=abc"      # query string preserved
  "/auth/whoami"
  "/classes"
  "/classes/42"
  "/dataset/clip.mp4"
  "/inference"
  "/jobs/7"
  "/upload/camera"
  "/upload/video"
  "/realtime/predict"
  "/realtime/models"
  "/realtime/health"
  # --- frontend: SPA pages, assets, and non-matching edges ---
  "/"
  "/login"
  "/labels"
  "/admin/labels/5"
  "/training"
  "/trash"
  "/assets/app-abc.js"
  "/logo.png"
  "/realtime"                            # EXACT SPA page -> frontend (NOT backend)
  "/realtime/other"                      # not an API verb -> frontend
  "/upload/other"                        # not camera/video -> frontend
  "/some/deep/spa/route"
)

echo
printf "%-38s | %-26s | %-26s | %s\n" "ROUTE" "root (P)" "/voya + P (stripped)" "VERDICT"
printf -- "---------------------------------------------------------------------------------------------------------------\n"
fails=0
for P in "${ROUTES[@]}"; do
  r_root="$(hit "$P")"
  r_voya="$(hit "/voya$P")"
  if [ "$r_root" = "$r_voya" ]; then verdict="OK"; else verdict="**MISMATCH**"; fails=$((fails+1)); fi
  printf "%-38s | %-26s | %-26s | %s\n" "$P" "$r_root" "$r_voya" "$verdict"
done
printf -- "---------------------------------------------------------------------------------------------------------------\n"

echo
echo "SPECIAL 1 — bare /voya must 301-redirect to /voya/ (when campus proxy keeps the prefix):"
loc="$(curl -s -o /dev/null -D - "http://localhost:$PORT/voya" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}')"
printf "   GET /voya  ->  HTTP %s   Location: %s\n" "$(code /voya)" "$loc"

# From here on, rate-limit tests hammer from ONE fixed client (fixed XFF) so the
# per-client bucket actually fills.
codef() { curl -s -o /dev/null -w '%{http_code}' -H "X-Forwarded-For: $1" "http://localhost:$PORT$2"; }

echo
echo "SPECIAL 2 — auth rate-limit (5r/s burst 10) fires on /api/v1/auth/* for ONE client:"
c200=0; c429=0
for _ in $(seq 1 25); do
  cc="$(codef 198.51.100.7 /voya/api/v1/auth/login)"
  [ "$cc" = "200" ] && c200=$((c200+1))
  [ "$cc" = "429" ] && c429=$((c429+1))
done
printf "   /voya/api/v1/auth/login x25 (1 client)  ->  200:%d  429:%d   (expect a mix)\n" "$c200" "$c429"
[ "$c429" -gt 0 ] || { echo "   !! auth limiter did NOT engage"; fails=$((fails+1)); }

echo
echo "SPECIAL 3 — global api_limit (30r/s burst 60) throttles a flood on the general API,"
echo "            but a DIFFERENT client is unaffected (per-real-client keying):"
N=300
urls="$(yes "http://localhost:$PORT/api/v1/classes" | head -n "$N" | tr '\n' ' ')"
flood="$(curl -Z --parallel-max 100 -s -o /dev/null -w '%{http_code}\n' \
         -H 'X-Forwarded-For: 198.18.0.9' $urls)"
n200=$(printf '%s\n' "$flood" | grep -cx 200)
n429=$(printf '%s\n' "$flood" | grep -cx 429)
printf "   /api/v1/classes x%d (1 client)  ->  200:%s  429:%s   (expect many 429)\n" "$N" "$n200" "$n429"
[ "$n429" -gt 0 ] || { echo "   !! api_limit did NOT engage"; fails=$((fails+1)); }
solo="$(codef 198.18.5.5 /api/v1/classes)"
printf "   single request from a fresh client  ->  HTTP %s (expect 200 — limit is per client)\n" "$solo"
[ "$solo" = "200" ] || { echo "   !! fresh client was wrongly throttled"; fails=$((fails+1)); }

echo
if [ "$fails" -eq 0 ]; then
  echo "RESULT: ✅ ALL ${#ROUTES[@]} routes route identically with and without /voya (prefix strip verified)."
else
  echo "RESULT: ❌ $fails route(s) MISMATCHED — see the table above."
fi
exit "$fails"
