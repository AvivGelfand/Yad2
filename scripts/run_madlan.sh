#!/bin/bash
# Scheduled local run of the MADLAN scraper (invoked by launchd hourly).
# Runs on its OWN job/lock/log, separate from the Yad2 run (run_local.sh), so
# the two never race on the Google Sheet — Madlan writes only its 'Madlan' tab.
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

# Only run during 07:00–23:00 Israel time (matches the Yad2 schedule).
HOUR=$(TZ='Asia/Jerusalem' date +%H)
if [ "$HOUR" -lt 7 ] || [ "$HOUR" -ge 23 ]; then
  echo "$(date '+%F %T') outside 07:00-23:00 IST (hour $HOUR) — skipping"
  exit 0
fi

# Skip cleanly if there's no internet (e.g., the Mac just woke from sleep).
# A real run fires on the next interval once connectivity returns.
if ! curl -sf -m 8 -o /dev/null https://www.google.com 2>/dev/null; then
  echo "$(date '+%F %T') no internet — skipping (will retry next interval)"
  exit 0
fi

# Prevent overlapping Madlan runs (a manual run + the scheduled one). Own lock,
# separate from the Yad2 lock. mkdir is atomic and portable. Take over a stale
# lock older than 55 min (longer than any healthy run, shorter than the interval).
mkdir -p "$REPO/data"
LOCKDIR="$REPO/data/.madlan.lock"
if [ -d "$LOCKDIR" ] && [ -z "$(find "$LOCKDIR" -mmin -55 2>/dev/null)" ]; then
  rmdir "$LOCKDIR" 2>/dev/null || true
fi
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "$(date '+%F %T') another Madlan run in progress — skipping"
  exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# Keep the Mac from idle-sleeping DURING the run (a mid-run sleep drops the
# network and kills the browser). caffeinate -i holds off idle sleep until the
# command exits.
CAFF=""
command -v caffeinate >/dev/null 2>&1 && CAFF="caffeinate -i"

echo "$(date '+%F %T') starting Madlan scrape (python: $PYTHON)"
$CAFF "$PYTHON" scripts/run_madlan.py 2>&1
RC=$?
echo "$(date '+%F %T') Madlan finished (exit $RC)"
exit "$RC"
