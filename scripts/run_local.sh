#!/bin/bash
# Scheduled local run of the Yad2 scraper (invoked by launchd every 30 min).
# launchd runs with a MINIMAL environment (no conda/shell profile, bare PATH),
# so we resolve an absolute Python and repo path here and don't rely on PATH.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1

# Python that has this project's requirements installed. Override with the
# YAD2_PYTHON env var. Find yours with:  which python
PYTHON="${YAD2_PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for cand in \
    "/Users/aviv.gelfand@gong.io/miniconda3/bin/python" \
    "$REPO/.venv/bin/python" \
    "$(command -v python3 || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then PYTHON="$cand"; break; fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "$(date '+%F %T') ERROR: no Python found — set YAD2_PYTHON to your python path"
  exit 1
fi

# Only run during 07:00–23:00 Israel time (matches the old GitHub schedule).
HOUR=$(TZ='Asia/Jerusalem' date +%H)
if [ "$HOUR" -lt 7 ] || [ "$HOUR" -ge 23 ]; then
  echo "$(date '+%F %T') outside 07:00-23:00 IST (hour $HOUR) — skipping"
  exit 0
fi

echo "$(date '+%F %T') starting scrape (python: $PYTHON)"
"$PYTHON" scripts/main.py
echo "$(date '+%F %T') finished (exit $?)"
