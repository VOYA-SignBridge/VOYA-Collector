#!/usr/bin/env bash
# Regenerates sample-hand.y4m, the fake-camera fixture used by the golden-path
# E2E suite (frontend/tests-e2e/golden-path.spec.ts).
#
# Not committed: it's a derived artifact of a real recorded sign-language
# frame from dataset/raw videos/, which is itself gitignored (see
# .gitignore:59). Regenerate it locally with the voya_backend image, which
# already has ffmpeg.
#
# A single clean frame, looped, rather than the full clip: MediaPipe Hands
# genuinely detects a hand in either case, but the ring buffer requires 40
# *consecutive* good detections (RealtimeRingBuffer minReadyFrames, see
# realtimeRingBuffer.ts) and clears itself on any single missed frame. The
# real clip has a brief low-confidence stretch (hand lowering/rising between
# rest and the sign) that resets the buffer every loop and never let it
# accumulate 40 in a row within a reasonable test timeout. A static,
# continuously well-formed pose has no such stretch — deterministic and fast,
# which is what this suite actually needs (it's proving the pipeline
# round-trips end to end, not testing recognition accuracy).

set -euo pipefail

SOURCE_VIDEO="${1:-dataset/raw videos/D0002.mp4}"
AT_SECONDS="${2:-2.5}"
STILL="frontend/tests-e2e/fixtures/still-hand.png"
OUT="frontend/tests-e2e/fixtures/sample-hand.y4m"

docker exec voya_backend ffmpeg -y \
  -ss "${AT_SECONDS}" -i "/workspace/${SOURCE_VIDEO}" -frames:v 1 \
  "/workspace/${STILL}"

docker exec voya_backend ffmpeg -y \
  -loop 1 -i "/workspace/${STILL}" -t 5 -pix_fmt yuv420p -r 24 \
  "/workspace/${OUT}"

rm -f "${STILL}"
echo "Wrote ${OUT}"
