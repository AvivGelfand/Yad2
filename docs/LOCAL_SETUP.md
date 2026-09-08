# Local scheduled scraping (launchd)

Yad2 blocks datacenter IPs (GitHub-hosted runners get a Radware "Bot Manager
Block"), so the scraper runs locally on your Mac (residential IP) on a schedule.
These steps set it up once.

All commands run from the repo root:

```bash
cd /Users/aviv.gelfand@gong.io/develop/code/misc/Yad2
```

## 1. Secrets for local runs

`main.py` auto-loads a `.env` file (via python-dotenv).

```bash
cp .env.example .env
# then edit .env and fill in:
#   SPREADSHEET_ID       (from your sheet URL)
#   TELEGRAM_BOT_TOKEN   (optional — leave blank to disable alerts)
#   TELEGRAM_CHAT_ID     (optional)
```

Put your Google service-account key at `config/credentials.json`.

## 2. Confirm the Python path

launchd runs with a minimal environment, so `scripts/run_local.sh` uses an
absolute Python. Check yours matches:

```bash
which python
```

If it is **not** `/Users/aviv.gelfand@gong.io/miniconda3/bin/python`, either edit
the `PYTHON=` line in `scripts/run_local.sh` or set the `YAD2_PYTHON` env var to
your python path.

Optional (better stealth than plain playwright):

```bash
pip install patchright && patchright install chromium
```

## 3. Test the wrapper once (right now)

```bash
bash scripts/run_local.sh
```

Should scrape and write to your sheet. Watch the output for a listing count > 0.

## 4. Install the 30-minute schedule

```bash
cp deploy/com.yad2.scraper.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.yad2.scraper.plist
launchctl list | grep com.yad2.scraper   # confirm it's registered
tail -f data/scraper.log                 # live logs
```

Runs every 30 minutes, gated to **07:00–23:00 Israel time**.

## Manage

```bash
# run immediately (bypass the 30-min wait)
launchctl start com.yad2.scraper

# stop / uninstall
launchctl unload ~/Library/LaunchAgents/com.yad2.scraper.plist

# after editing the plist, reload it
launchctl unload ~/Library/LaunchAgents/com.yad2.scraper.plist
launchctl load   ~/Library/LaunchAgents/com.yad2.scraper.plist
```

## Behavior when the Mac is off / asleep / offline

The scraper is **state-based and idempotent**, so intermittent uptime is fine —
it doesn't need to catch every 30-minute window:

- Each run fetches the *current* live listings and upserts them to the sheet.
  Durable state lives in `data/seen_properties.json` (new-vs-seen) and the
  sheet's lifecycle columns — so a missed run just means "poll skipped", never
  broken/duplicated state.
- **Asleep:** launchd does not queue missed intervals; it fires **once** on
  wake. With `RunAtLoad=true` it also runs promptly on login. Either way it
  re-syncs to whatever is live at that moment.
- **Off all day:** same — on next login/wake it runs and re-syncs.
- **Offline when a run fires:** the wrapper's connectivity check skips cleanly
  (logged as "no internet — skipping"); the next interval recovers.
- **Idle-sleep mid-run:** prevented — the run executes under `caffeinate -i`,
  so a started scrape completes without the network dropping under it.

**The one thing downtime can't recover:** a listing that is posted *and removed
entirely* while you're down is never seen, so no notification for it. That's
inherent to any polling scraper — only a continuous/server-side feed avoids it.

To reduce that window, keep the Mac awake during the day (System Settings →
prevent sleep, or a background `caffeinate -s`), or run in the cloud (below).

## Notes

- Logs go to `data/scraper.log`.
- Cloud alternative: set a `YAD2_PROXY` repo secret (Israeli residential proxy)
  or use a self-hosted runner, then uncomment the `schedule:` in
  `.github/workflows/scraper.yml`.
