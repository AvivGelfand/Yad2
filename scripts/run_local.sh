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

# Skip cleanly if there's no internet (e.g., the Mac just woke from sleep).
# This is a clean SKIP, not a failure — a real run fires on the next interval
# once connectivity returns, and the state-based scraper re-syncs then.
if ! curl -sf -m 8 -o /dev/null https://www.google.com 2>/dev/null; then
  echo "$(date '+%F %T') no internet — skipping (will retry next interval)"
  exit 0
fi

# Prevent overlapping runs (a manual run + the scheduled one) that interleave
# the log and double-hit the WAF. mkdir is atomic and portable (macOS has no
# flock). Take over a stale lock older than 55 min (longer than any healthy run).
mkdir -p "$REPO/data"
LOCKDIR="$REPO/data/.scraper.lock"
if [ -d "$LOCKDIR" ] && [ -z "$(find "$LOCKDIR" -mmin -55 2>/dev/null)" ]; then
  rmdir "$LOCKDIR" 2>/dev/null || true
fi
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "$(date '+%F %T') another run in progress — skipping"
  exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# Keep the Mac from idle-sleeping DURING the run (a mid-run sleep drops the
# network and kills the scrape). caffeinate -i holds off idle sleep until the
# command exits; it does NOT keep the Mac awake to catch future runs.
CAFF=""
command -v caffeinate >/dev/null 2>&1 && CAFF="caffeinate -i"

# Telegram heartbeat: keep ONE pinned status message showing the last real run,
# so you can tell at a glance when the scraper last ran and how it went. Creds
# are read straight from .env (main.py loads them itself via dotenv). No-ops
# silently if creds are absent. Never aborts the run (all calls best-effort).
# ponytail: this reports actual scrape attempts only — skips (outside hours / no
# internet / lock) leave the last-run line untouched, and a scraper that never
# fires can't self-report. Add an external dead-man's switch if you need that.
TG_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$REPO/.env" 2>/dev/null | cut -d= -f2-)
TG_CHAT=$(grep -E '^TELEGRAM_CHAT_ID=' "$REPO/.env" 2>/dev/null | cut -d= -f2-)
TG_IDFILE="$REPO/data/.telegram_status_id"

send_status() {  # $1 = message text; edits the pinned message, else sends anew
  [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ] || return 0
  local text="$1" api="https://api.telegram.org/bot$TG_TOKEN" mid resp
  mid=$(cat "$TG_IDFILE" 2>/dev/null || true)
  if [ -n "$mid" ]; then
    resp=$(curl -s -m 10 "$api/editMessageText" \
      --data-urlencode "chat_id=$TG_CHAT" \
      --data-urlencode "message_id=$mid" \
      --data-urlencode "text=$text" 2>/dev/null || true)
    [ "$(printf '%s' "$resp" | jq -r '.ok' 2>/dev/null)" = "true" ] && return 0
  fi
  # No stored id, or the edit failed (message deleted/expired) — send a fresh one.
  resp=$(curl -s -m 10 "$api/sendMessage" \
    --data-urlencode "chat_id=$TG_CHAT" \
    --data-urlencode "text=$text" 2>/dev/null || true)
  mid=$(printf '%s' "$resp" | jq -r '.result.message_id // empty' 2>/dev/null || true)
  [ -n "$mid" ] && printf '%s' "$mid" > "$TG_IDFILE"
}

echo "$(date '+%F %T') starting scrape (python: $PYTHON)"
# tee so the output still lands in the log AND we can read this run's counts.
$CAFF "$PYTHON" scripts/main.py 2>&1 | tee "$REPO/data/.last_run_output"
RC=${PIPESTATUS[0]}
echo "$(date '+%F %T') finished (exit $RC)"

# Update the pinned Telegram status line with this run's result.
COUNTS=$(grep -oE '[0-9]+ new / [0-9]+ total' "$REPO/data/.last_run_output" 2>/dev/null | tail -1)
rm -f "$REPO/data/.last_run_output"
STAMP=$(TZ='Asia/Jerusalem' date '+%Y-%m-%d %H:%M %Z')
[ "$RC" -eq 0 ] && ICON="🟢" || ICON="🔴"
send_status "$ICON Yad2 scraper
Last run: $STAMP
exit $RC${COUNTS:+ · $COUNTS}"
exit "$RC"
