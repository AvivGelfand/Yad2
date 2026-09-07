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

## Notes

- **The Mac must be awake** when a run fires, or that run is skipped. Disable
  sleep during the day, or run under `caffeinate`.
- Logs go to `data/scraper.log`.
- Cloud alternative: set a `YAD2_PROXY` repo secret (Israeli residential proxy)
  or use a self-hosted runner, then uncomment the `schedule:` in
  `.github/workflows/scraper.yml`.
