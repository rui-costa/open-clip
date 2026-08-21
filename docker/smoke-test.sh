#!/usr/bin/env bash
#
# Starts the composed stack and checks that it actually works, rather than that
# it merely built. Everything here has failed at least once in a container that
# built cleanly: a Python version that cannot evaluate the app's annotations,
# an OpenCV without libGL, a caption font resolving to a monospace face, a bind
# mount the container cannot write.
#
# Usable by hand as well as by CI:
#   ./docker/smoke-test.sh              # build, test, stop the containers
#   KEEP_UP=1 ./docker/smoke-test.sh    # leave the stack running afterwards
#
# The named volumes are left alone unless DOWN_VOLUMES=1, because one of them
# holds the YouTube OAuth token and another the downloaded model weights. CI
# passes it; a local run should not have to re-authorise afterwards.
#
set -euo pipefail

BACKEND_URL="http://localhost:${BACKEND_PORT:-8000}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT:-5173}"
KEEP_UP="${KEEP_UP:-0}"
DOWN_VOLUMES="${DOWN_VOLUMES:-0}"
FAILURES=0

cd "$(dirname "$0")/.."

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

check() {
    # check <name> <expected> <actual>
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (expected '$2', got '$3')"; fi
}

cleanup() {
    local status=$?
    if [ "$status" -ne 0 ] || [ "$FAILURES" -ne 0 ]; then
        echo
        echo "--- backend logs ---"
        docker compose logs --no-color --tail 100 backend || true
        echo "--- frontend logs ---"
        docker compose logs --no-color --tail 40 frontend || true
    fi
    if [ "$KEEP_UP" != "1" ]; then
        if [ "$DOWN_VOLUMES" = "1" ]; then
            docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
        else
            docker compose down --remove-orphans >/dev/null 2>&1 || true
        fi
    fi
}
trap cleanup EXIT

echo "==> Building"
docker compose build

echo "==> Starting (waiting for both healthchecks)"
# --wait fails the command if a container never reaches healthy, so the
# healthchecks in the two Dockerfiles are themselves part of the test.
docker compose up --detach --wait --wait-timeout 180

echo
echo "==> API"
check "/health returns ok" \
    '{"status": "ok"}' \
    "$(curl -sf "$BACKEND_URL/health")"

check "/projects returns a list" \
    "list" \
    "$(curl -sf "$BACKEND_URL/projects" | python3 -c 'import json,sys; print(type(json.load(sys.stdin)).__name__)')"

check "/resolutions is served from the mounted config" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$BACKEND_URL/resolutions")"

# The sample project is committed, so its media is there to range-request. This
# is the path every clip preview in the UI goes through.
SAMPLE_ID="00000000-0000-0000-0000-000000000000"
check "media range request returns partial content" \
    "206" \
    "$(curl -s -o /dev/null -w '%{http_code}' -H 'Range: bytes=0-1023' \
        "$BACKEND_URL/projects/static/$SAMPLE_ID/original.mp4")"

echo
echo "==> Frontend"
check "index is served" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$FRONTEND_URL/")"

# React Router owns these paths; nginx has to answer with the app, not a 404.
check "deep link falls back to the app" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$FRONTEND_URL/settings")"

# The API address is baked in at build time, so a broken build arg only shows
# up as a frontend that talks to nothing. Assert it reached the bundle.
# Read each response into a variable before matching it. Piping curl into
# `grep -q` under `set -o pipefail` reports failure even on a match, because
# grep exits at the first hit and curl dies of SIGPIPE writing the rest.
INDEX_HTML=$(curl -sf "$FRONTEND_URL/")
BUNDLE_PATH=$(printf '%s' "$INDEX_HTML" | grep -o '/assets/index-[^"]*\.js' | head -1 || true)
if [ -z "$BUNDLE_PATH" ]; then
    fail "could not find the JS bundle in index.html"
else
    BUNDLE=$(curl -sf "$FRONTEND_URL$BUNDLE_PATH" || true)
    case "$BUNDLE" in
        *"localhost:${BACKEND_PORT:-8000}"*) pass "VITE_API_URL is baked into the bundle" ;;
        *) fail "bundle does not reference the backend URL" ;;
    esac
fi

echo
echo "==> Backend runtime dependencies"
# Each import here has its own system package behind it; a missing one is an
# ImportError at the first clip, not at build.
docker compose exec -T backend python - <<'PY' && pass "imports, fonts, weights and ffmpeg" || fail "runtime dependency check"
import subprocess
import sys
from pathlib import Path

problems = []

import cv2  # needs libgl1, libglib2.0-0
import whisper  # noqa: F401
from ultralytics import YOLO

# The weights are baked in; loading them proves both the file and torch.
YOLO("root/yolov8n.pt")

from backend.src.infrastructure.font_metrics import resolve_face

# fontconfig has to resolve to a real file, and "Arial Black" must not land on
# a monospace face - which is what it does without docker/fonts-aliases.conf.
for family in ("Arial", "Arial Black"):
    face = resolve_face(family)
    if face.path is None or not Path(face.path).is_file():
        problems.append(f"{family!r} resolved to no file")
    elif "Mono" in face.path.name:
        problems.append(f"{family!r} resolved to a monospace face: {face.path.name}")

# libass is what burns the captions in; ffmpeg without it renders clips with no
# subtitles and no error the app can see.
filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                         capture_output=True, text=True).stdout
if " subtitles " not in filters:
    problems.append("ffmpeg has no subtitles filter (built without libass)")

# An actual encode of the sample video, which is what every clip render does.
sample = "projects/00000000-0000-0000-0000-000000000000/original.mp4"
encode = subprocess.run(
    ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", sample,
     "-t", "1", "-c:v", "libx264", "-c:a", "aac", "/tmp/smoke.mp4"],
    capture_output=True, text=True,
)
if encode.returncode != 0 or not Path("/tmp/smoke.mp4").stat().st_size:
    problems.append(f"ffmpeg encode failed: {encode.stderr.strip()[-300:]}")

# OpenCV plus the weights, on a real frame.
from backend.src.infrastructure.video_engine import OpenCVVideoEngine
if OpenCVVideoEngine("root/yolov8n.pt").get_subject_center(sample, 0.5) is None:
    problems.append("YOLO found no subject in the sample frame")

for problem in problems:
    print(f"    {problem}", file=sys.stderr)
sys.exit(1 if problems else 0)
PY

echo
echo "==> Writable state"
# The app saves settings, secrets and project media to these. A uid mismatch
# between the image and the checkout shows up here and nowhere earlier.
for mount in /app/projects /app/backend/config /app/backend/logs /app/backend/youtube_credentials; do
    if docker compose exec -T backend sh -c "touch $mount/.smoke && rm $mount/.smoke" 2>/dev/null; then
        pass "writable: $mount"
    else
        fail "not writable: $mount"
    fi
done

# Secrets must not be in the image. `COPY backend/ ./backend/` picks them up
# unless .dockerignore keeps them out. Run the image directly rather than
# through compose: compose would mount the real backend/config over the top and
# the file would appear either way.
for secret in backend/config/secrets.json backend/youtube_credentials/youtube_credentials.json; do
    if docker run --rm open-clip-backend sh -c "test -e /app/$secret" 2>/dev/null; then
        fail "$secret was baked into the image"
    else
        pass "not in the image: $secret"
    fi
done

echo
if [ "$FAILURES" -ne 0 ]; then
    echo "$FAILURES check(s) failed."
    exit 1
fi
echo "All checks passed."
