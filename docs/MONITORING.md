# Monitoring the local scraper (launchd)

The scheduled scraper runs via launchd (see [LOCAL_SETUP.md](LOCAL_SETUP.md)).
Every run — success, failure, or skipped — appends to **one log file**:

```
data/scraper.log
```

(That's the `StandardOutPath`/`StandardErrorPath` set in
`deploy/com.yad2.scraper.plist`.) All commands below run from the repo root.

## Anatomy of a run in the log

`scripts/run_local.sh` brackets each run with timestamped markers:

```
2026-09-08 08:30:01 starting scrape (python: /Users/.../miniconda3/bin/python)
... scraper output (searches, listings, notifications) ...
2026-09-08 08:31:14 finished (exit 0)
```

- **`starting scrape` / `finished (exit N)`** — the timestamps tell you *when*
  a run happened and how long it took.
- **`exit 0`** = success. **`exit` non-zero** = failure.
- **`outside 07:00-23:00 IST (hour H) — skipping`** = the run fired but was
  intentionally skipped (outside operating hours). Not a failure.
- A blocked run (e.g. run from a datacenter IP) prints
  `❌ Yad2 anti-bot block ...` before exiting non-zero.

## Watch logs live

```bash
tail -f data/scraper.log          # follow in real time
tail -n 200 data/scraper.log      # last ~200 lines
```

## When did each run happen?

```bash
grep "starting scrape" data/scraper.log         # start time of every run
grep "finished (exit"  data/scraper.log         # end time + exit code of every run
grep -E "starting scrape|finished \(exit"       data/scraper.log   # both, interleaved
```

## Which runs failed?

```bash
# Failed runs (non-zero exit):
grep -nE "finished \(exit [1-9][0-9]*\)" data/scraper.log

# Runs blocked by Yad2's anti-bot (should be none from a residential IP):
grep -n "anti-bot block" data/scraper.log

# Quick tally of successes vs failures:
grep -c "finished (exit 0)" data/scraper.log            # successes
grep -cE "finished \(exit [1-9]" data/scraper.log       # failures
```

To read the full output of the most recent run:

```bash
# everything since the last "starting scrape"
awk '/starting scrape/{buf=""} {buf=buf $0 ORS} END{printf "%s", buf}' data/scraper.log
```

## launchd-level status

```bash
launchctl list | grep com.yad2.scraper      # is it registered / last state
launchctl print gui/$(id -u)/com.yad2.scraper | grep -iE "state|last exit|runs"
```

> Note: the middle column of `launchctl list` shows the **wrapper's** exit code,
> which is almost always `0` (the wrapper logs the result and exits cleanly). So
> **use `data/scraper.log` — not `launchctl` — to tell which scrapes failed.**

## Failure alerts via Telegram

If `NOTIFY_ON_ERROR=true` in your `.env`, the scraper also sends a Telegram
message on errors — so you don't have to watch the log to catch failures.

## Housekeeping

`data/scraper.log` grows unbounded. Trim it occasionally:

```bash
: > data/scraper.log                     # empty it
# or keep only the last 2000 lines:
tail -n 2000 data/scraper.log > data/scraper.log.tmp && mv data/scraper.log.tmp data/scraper.log
```
