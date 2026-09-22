# Anti-Bot / Challenge Handling

How Yad2 blocks scrapers, how this project fetches around it, and how we treat
challenges when they hit. This is the single place for anti-bot knowledge —
other docs (`README.md`, `docs/LOCAL_SETUP.md`, `docs/GITHUB_ACTIONS_SETUP.md`)
only reference it.

> Status (2026-09-22): scraping works from a **residential IP** with
> `patchright`. Item-page challenges are frequent but usually recover on retry.
> A run can still abort if a *single* item stays blocked through all retries —
> see [Known failure mode](#known-failure-mode-one-blocked-item-kills-the-run).

---

## 1. What Yad2 runs

Yad2 is behind **Radware Bot Manager** (the challenge page title is literally
`Radware Bot Manager Captcha`). It defends on two layers:

1. **ASN / IP reputation.** Datacenter and CI ranges — including GitHub-hosted
   runners — are hard-blocked regardless of the browser. You *must* fetch from a
   residential IP (home connection, self-hosted runner, or an Israeli
   residential proxy via `YAD2_PROXY`). See `scripts/yad2_fetch.py:9-13`.
2. **JS challenge.** Plain HTTP clients (`requests`, `curl_cffi`, `httpx`) never
   execute the challenge JS that mints the access cookie, so they get a
   403/interstitial even from a good IP. A real browser engine does execute it.
   The interstitial is often served with **HTTP 200**, not 403 — so status code
   alone is not a reliable block signal (`scripts/yad2_fetch.py:3-7`).

The page structure also changed: results are now server-rendered into a
`<script id="__NEXT_DATA__">` blob, and search requires a `region`/`area`
parameter. Presence of `__NEXT_DATA__` is our "this is a real page" signal.

## 2. How we fetch

`scripts/yad2_fetch.py` — `BrowserSession`:

- **Engine:** `patchright` (stealth-patched Playwright), falling back to plain
  `playwright`. One long-lived `BrowserSession` per run — never per request
  (`yad2_fetch.py:101-108`).
- **Custom UA:** a real desktop-Chrome UA. The default headless
  `HeadlessChrome` UA is auto-blocked and bounced to `validate.perfdrive.com`
  (`yad2_fetch.py:59-64`).
- **Context:** `locale=he-IL`, viewport 1366×900, real Chrome channel if present
  (`yad2_fetch.py:118-143`).
- **Proxy:** optional, from `YAD2_PROXY` / `YAD2_PROXY_USERNAME` /
  `YAD2_PROXY_PASSWORD` (`yad2_fetch.py:25-46`).
- **Wait strategy:** `wait_until="domcontentloaded"` then wait for the
  `#__NEXT_DATA__` selector (up to 15 s) plus a `settle` delay. `networkidle` is
  avoided — Yad2's long-lived connections never idle (`yad2_fetch.py:145-164`).

### Retry loop (`fetch()`, `yad2_fetch.py:165-201`)

For each request, up to `retries=3` attempts, `retry_wait=6s` between them:

- **Navigation error** (goto timeout, transient drop) → new context, wait, retry.
- **Connectivity error** (`ERR_INTERNET_DISCONNECTED`, `ERR_NAME_NOT_RESOLVED`,
  …) → **fail fast, no retry** — a dead link can't be fixed by retrying, and
  retrying every listing wastes ~160s per run (`yad2_fetch.py:84-98,183-186`).
- **Block detected** → new context, wait, retry.
- If all retries are exhausted, `fetch()` **returns the last (blocked)
  status/html without raising** — the caller decides what to do.

## 3. How we detect a block

`scripts/yad2_parse.py:62-75` — `is_blocked(text, status)`:

1. `status in (401, 403, 429)` → blocked.
2. Empty body → blocked.
3. `__NEXT_DATA__` present → **not** blocked (short-circuit).
4. Otherwise scan the first 10 KB for signatures: `radware`, `shieldsquare`,
   `perfdrive`, `px-captcha`, `captcha-delivery`, `403 forbidden`,
   `attention required`, `are you a robot`.

Deliberately signature-based, not "no `__NEXT_DATA__`": a real page that merely
hasn't finished loading the data blob (correct Hebrew title, HTTP 200, no blob
yet) is **not** a block. Flagging those spammed false errors — fixed in
`8fc01d5`.

## 4. Known failure mode: one blocked item kills the run

This is the root cause of the `2026-09-22 12:35:36 finished (exit 1)` run.

**Symptom.** The run scraped 51 unique listings and saved photos for ~48 of
them, then died with:

```
Scraping individual listing page: .../item/pfupzslg
  ⚠️ blocked (HTTP 200); retrying with a fresh context in 6s (1/3)...
  ⚠️ blocked (HTTP 200); retrying with a fresh context in 6s (2/3)...
❌ Yad2 blocked during item scraping: Yad2 anti-bot block on item .../pfupzslg.
   HTTP 200 bytes=18623 next_data=False title='Radware Bot Manager Captcha'
No listings found across all searches
2026-09-22 12:35:36 finished (exit 1)
```

**Chain of events:**

1. Item `pfupzslg` was served the Radware captcha (HTTP 200, no `__NEXT_DATA__`)
   on all 3 attempts. `fetch()` returns the blocked HTML.
2. `scrape_listing_page()` re-checks `is_blocked` → true → **raises**
   `Yad2Blocked` (`scraper.py:119-122`).
3. `scrape_listings_pages()` catches `Yad2Blocked` and **re-raises** it —
   *"A block is systemic, not a per-listing glitch — surface it."*
   (`scraper.py:351-353`).
4. `run_multi_search()` catches it and **returns an empty DataFrame**
   (`scraper.py:277-281`).
5. `main.py:22-24` sees the empty frame → prints `No listings found across all
   searches` → `exit(1)`.

**Why it's fragile.** The "a block is systemic" assumption (in place since the
Sept 7 patchright rewire, `5f30fc3`) is wrong for *item* pages. In the same run,
~48 other items hit the identical HTTP-200 challenge on their first attempt and
**recovered on retry** — proving the challenge is *probabilistic per request*,
not a session-wide ban. Aborting on the one item that lost the retry lottery
throws away an otherwise-successful harvest (all scraped rows, all photos, all
notifications). The assumption is only correct for **search/feed** pages: if the
feed is blocked, every subsequent request would be too.

### Scale of the challenge pressure

Over the whole `data/scraper.log` (2026-09-07 → 09-22): **1267** `blocked (HTTP …)`
retry lines and **643** `fetch error` retries. The challenge rate on item pages
is now high enough that a first-attempt block is the norm, not the exception —
the retry loop is what's carrying the scraper. That makes an unrecoverable
single-item block a matter of *when*, not *if*.

## 5. Handling strategy

### Principle

Distinguish **systemic** blocks (feed/session-wide → abort loudly) from
**probabilistic** per-item blocks (skip the item, keep the run).

### Applied (2026-09-22)

1. **A single item block no longer aborts the run.** In
   `scrape_listings_pages()`, a `Yad2Blocked` from an item is now treated like
   any other failed listing (added to `failed_listings`) and the loop continues.
2. **Streak guard for a genuinely flagged session.** A module of
   `consecutive_blocks` counts item blocks with no success between them; it
   resets on any successful (or cached) scrape. At
   `Yad2MultiSearchScraper.BLOCK_STREAK_LIMIT` (=5) consecutive blocks the run
   **stops early but returns everything scraped so far** (via `break`, not a
   raise) — it does not discard the harvest, and sends an error notification.
3. **Feed-page abort unchanged.** A `Yad2Blocked` from `fetch_listings()` still
   stops the run (`scraper.py:231-235`) — that one is genuinely systemic.

Covered by `tests/test_item_block_skip.py` (single block skipped + harvest kept;
streak stops early without discarding). Not done: raising item `retries` /
adding jitter — deferred as a separate lever.

## History — how we got here

Reconstructed from prior working sessions (2026-09-07 → 09-22).

### Timeline

- **Baseline (pre-09-07):** a plain `requests`-based scraper ran on
  GitHub-hosted Actions every 30 min, reading `props.pageProps.feed` from
  `__NEXT_DATA__`. It worked.
- **09-07 — two simultaneous breaks.** Runs started returning `Total listings
  found: 0` / `exit 1`. Diagnosis found (a) a **Radware AppWall/Bot Manager**
  block (`Server: rdwr`) — a 403 "Transaction ID" page from datacenter, or a
  200 "Radware Page" challenge with no `__NEXT_DATA__`; and (b) a **site
  restructure**: the feed moved from `props.pageProps.feed` to
  `props.pageProps.dehydratedState.queries[].state.data` (React-Query cache) /
  the `gw.yad2.co.il/realestate-feed` gateway, and **`region`/`area` became
  required** (400 without it).
- **09-07 — proved it's a JS challenge, not IP/TLS.** Plain `curl` and
  `curl_cffi` (JA3 impersonation) got 403 even from the user's **home**
  connection. Conclusion: Radware serves 403 to any client that doesn't execute
  the challenge JS to earn the validation cookie.
- **09-07 — datacenter is doomed, residential works.** patchright pulled 44
  listings *once* from the datacenter IP, then 403 (WAF flags the IP after a
  request or two). From a **residential Mac** it worked cleanly (43 listings +
  item detail). GitHub-hosted CI was proven hard-blocked at the network layer
  ("Radware Bot Manager Block").
- **09-08 → 09-15:** failures shifted from blocks to **operational** issues
  (Mac asleep → `ERR_INTERNET_DISCONNECTED`; `networkidle` timeouts) and a
  false-positive block alert on half-loaded pages (fixed `8fc01d5`). By **09-15**
  the **residential Mac itself began getting blocked on nearly every item
  intermittently** — the residential advantage started eroding.
- **09-16 → 09-18:** challenge title shifted from "Block" to
  "**Captcha**". Confirmed the **image CDN `img.yad2.co.il` is outside the WAF**
  (plain `requests` → 200 JPEG), so photos download even when item pages block.
- **09-22:** the `exit 1` run in §4 — rising item-page challenge pressure, not a
  code change, tipped the long-standing all-or-nothing abort into a real failure.

### Mitigations tried

| Mitigation | Verdict |
|---|---|
| Plain `requests` / `httpx` HTTP2 / `requests.Session` + warm-up | ❌ 403 — never executes challenge JS |
| `curl_cffi` TLS/JA3 impersonation (chrome/safari variants) | ❌ 403 even from residential — not a fingerprint gate |
| Alternate/mobile endpoints (`gw.`/`api.yad2.co.il`, mobile headers) | ❌ same edge WAF (403) / TCP refused |
| Scrapling `StealthyFetcher` / Scrapy + scrapy-playwright | ⚠️ engine works; still 403 from datacenter |
| **patchright stealth engine (residential IP)** | ✅ **the winner — shipped** |
| Custom desktop-Chrome UA (avoid `HeadlessChrome`) | ✅ required |
| `he-IL` locale, 1366×900 viewport, real Chrome channel | ✅ part of working profile |
| One long-lived `BrowserSession` per run | ✅ |
| `domcontentloaded` + wait-for-`#__NEXT_DATA__` + settle (replaced `networkidle`) | ✅ |
| Fresh-context retry on block (`retries=3`, `retry_wait=6s`) | ⚠️ recovers residential/transient; can't un-flag a datacenter IP |
| Fail-fast on connectivity errors | ✅ saves ~160s/run on a dead link |
| Signature-based `is_blocked` (not "no `__NEXT_DATA__`") | ✅ after 2 false-positive iterations |
| Image CDN via plain `requests` | ✅ CDN is outside WAF |
| `YAD2_PROXY` residential-proxy support | ⚠️ wired, **never tested** (no proxy purchased) |

### Rejected

- **Free GitHub-hosted CI scraping** — proven dead (network-layer IP block); no
  stealth/header/retry change beats it.
- **Self-hosted GH runner** — offered; never registered → jobs queued forever →
  abandoned CI for local `launchd` (`scripts/run_local.sh` +
  `deploy/com.yad2.scraper.plist`, every 30 min, 07:00–23:00 IST).
- **Residential proxy on CI** — the one lever that would revive cloud scraping;
  deferred on cost. Code supports it via `YAD2_PROXY` if ever supplied.
- **Captcha-solving services (2captcha, etc.)** — never attempted; the whole
  strategy is "let a real browser pass the JS challenge," not solve a visible
  captcha.

## 6. Operational runbook

- **Run from a residential IP.** Datacenter/CI/GitHub-hosted = hard ASN block.
  For CI, use a self-hosted runner on a home connection or set `YAD2_PROXY` to an
  Israeli residential proxy.
- **Engine check:** the log prints `🌐 Browser engine: patchright`. If it says
  `playwright`, install patchright: `pip install patchright && patchright install chromium`.
- **Reading the log** (`data/scraper.log`):
  - `blocked (HTTP 200); retrying …` — normal, per-request challenge; recovers.
  - `Yad2 blocked during item scraping … Radware Bot Manager Captcha` +
    `No listings found across all searches` + `exit 1` — the abort described in
    §4.
  - `no internet — skipping` / `connectivity lost` — machine offline, not a block.
  - `outside 07:00-23:00 IST … skipping` — scheduler gate, not a failure.
- **Photos** download fine even when item detail is blocked, because the image
  CDN is **not** behind the WAF.
