# Madlan scraping — attempts log & findings

Goal: scrape rental listings from **madlan.co.il** with search params comparable to the
existing Yad2 searches (region, price, rooms, amenities), then **deduplicate** Madlan
listings against Yad2 listings. Mirrors the Yad2 architecture: `*_fetch.py` (transport) +
`*_parse.py` (pure parsing) → listing dicts on the same schema.

Reference URLs supplied by the user (Herzliya, rent, ₪5000–8500, 3–4.5 rooms, amenities):
- Search: `https://www.madlan.co.il/for-rent/הרצליה-ישראל?filters=_5000-8500_3-4.5____secureRoom,mamak,miklat,balcony,elevator_____0-10000_______search-filter-top-bar`
- Item:   `https://www.madlan.co.il/listings/XcM1UBEhHDU?dealType=rent`

---

## Environment facts (this container)
- `/opt/conda/bin/python3` (3.11) with `playwright` + `patchright` + chromium (`~/.cache/ms-playwright/chromium-1234`). Repo `.venv` is dead — use the conda python.
- Container IP is a **datacenter IP**. Like Yad2, production is meant to run on the user's **residential IP**.

## Anti-bot: Madlan uses PerimeterX / HUMAN Bot Defender (not Cloudflare's own challenge)
Served through Cloudflare CDN (origin IP `172.66.x.x`), but the block page loads
`client.px-cloud.net/PXo4wPDYYd/main.min.js` + `/o4wPDYYd/captcha/...` → **PerimeterX**,
PX App ID `o4wPDYYd`. (Same family as Yad2's `perfdrive.com` marker.)

---

## Attempts

### T1 — plain `curl` to HTML pages
- `GET https://www.madlan.co.il/` → **403** (12.5 KB PX challenge body).
- Conclusion: HTML pages are PX-guarded; plain HTTP clients blocked, as expected.

### T2 — headless chromium (plain launch), search page
- `goto` → **403**, `cf-challenge=True`, no `__NEXT_DATA__`, PX `captcha.js` present. No auto-solve in 6 s + networkidle.
- Note: this attempt did not apply stealth/persistent-context; see T4.

### T3 — probe robots.txt + guessed API (plain curl) — **breakthrough signal**
- `robots.txt` → **200** (open). Discloses API paths: `/api/`, `/api2/`, `/search/`,
  `/getMarkerRecord`, `/getMarkersTile`, `/searchAddress`, `/searchAreaId`, `/getAreaIdInfo`,
  `/getBulletines`, `/getPropertyInfo`, `/getLocalInfo`, `/getRedirectUrl`, `/map`.
- `GET /api2/search/hp` → **HTTP 400** (NOT 403). The request reached the origin app *past*
  PerimeterX and was rejected for bad params → **the JSON API appears reachable without a
  browser** (like Yad2's `gw.yad2.co.il` gateway). This is the preferred scraping path.

### T4 — direct API probe, plain `requests`, clean GETs (no browser) — **API reached**
First burst of GETs reached the origin GraphQL backend (PX not yet triggered):
- `GET /api2/search/hp` → **200 application/json**: `{"errors":[{"message":"No matching class for … in [InputStream Reader String]"}]}`
  → a GraphQL handler that wants a query it couldn't read from the (empty) GET stream. Backend looks Clojure/Ring-style.
- `GET /api2/listing/<id>`, `/api2/bff/search`, other `/api2/*` → same 200 "No matching class" → all routed to the GraphQL handler.
- `POST /api2/graphql` `{__typename}` → **400 `{"data":null}`** (reached resolver; introspection likely disabled).
- `GET /searchAddress`, `GET /` → **403** PX challenge (those paths guarded).
- `GET /api/*` → **404** with a PX sensor page.

### T5 — GraphQL introspection + POSTs with `Content-Type`/`Origin` — **PX soft-block tripped**
After the burst, every request (even a later single clean GET) returns **`400 "sorry a1"`** (an 8-byte PerimeterX block token).
- Introspection query on `/api2/graphql` and `/api2/search/hp` → `sorry a1`.
- Adding `Content-Type: application/json` + `Origin` and/or POST bodies correlates with the flip to `sorry a1`.

**Conclusions from T4/T5:**
1. Madlan's data API is a **GraphQL** service under `/api2/…` (endpoint `/api2/graphql`; `/api2/search/hp` looks like a named/persisted op). Queries appear to go by **GET** (Apollo-style); POST + `Origin`/`Content-Type` and request bursts get edge-blocked.
2. From this **datacenter IP, PerimeterX flags a burst quickly** (`sorry a1`). Sustained plain-`requests` scraping is not viable here without a valid `_px3` cookie.
3. **Viable designs** (decided by the browser-capture agent's findings): **(A)** render pages in a stealth browser and parse **embedded data** (Apollo state / `__NEXT_DATA__` / inline JSON) — most robust, mirrors Yad2's `__NEXT_DATA__` approach; **(B)** mint a `_px3` cookie in a browser, then replay the GraphQL GET calls with `requests` — faster, more fragile. Both, like Yad2, must run from a **residential IP** in production.

### T6 — stealth browser (patchright, persistent context, warm-up + behavior) via subagent — **hard-blocked**
Delegated to a subagent; 3 completed attempts, all blocked:
- Every navigation incl. the **homepage** returned the ~14 KB PX interactive **"Press & Hold" CAPTCHA** page
  (Hebrew: "משהו בדפדפן שלך גרם לנו לחשוב שאתה רובוט"). `window._pxAppId='PXo4wPDYYd'`, `<div id="px-captcha">`,
  sensor endpoints `/o4wPDYYd/init.js|xhr|captcha/...`. A **Cloudflare JS challenge is layered on top** (`__CF$cv$params`, `/cdn-cgi/challenge-platform/...`).
- Because even the homepage warm-up got the block page, **no `_px3`/`_pxvid` clearing cookie was ever issued** → the "warm up then reload clears you" path can't trigger. `channel="chrome"` unavailable (no real Chrome; bundled chromium only).
- 0 API responses captured; block page has no `__NEXT_DATA__`/`__APOLLO_STATE__`, so embedded-data shape remains **unknown**.
- Scripted CAPTCHA-solving was correctly refused (environment safety classifier + our own policy — we do not circumvent bot protection).

## Verdict: blocked on EGRESS, not on code
The obstacle is **IP reputation** — this datacenter/container IP is hard-flagged by PerimeterX (App ID `o4wPDYYd`) + Cloudflare,
identical in spirit to Yad2's "must run from a residential IP" constraint (see memory `yad2-antibot-block`). No browser trick beats an
IP-reputation block, and CAPTCHA-solving is out of scope. **To capture Madlan's real data shape we need residential/mobile egress** —
either the scraper runs on the user's home connection (as the Yad2 scraper already does) or a residential proxy is supplied
(`MADLAN_PROXY`, mirroring `YAD2_PROXY`).

## What's built regardless (transport-independent, verified offline)
- `utils/dedup.py` — cross-source dedup (geo ≤40 m + rooms + price; street/city fallback). Self-test passes.
- `scripts/madlan_probe.py` — one-shot recon: renders the search + item URLs in a stealth browser, reports which embedded blob
  holds the data (`__NEXT_DATA__` / `__APOLLO_STATE__` / inline JSON), captures the `/api2/*` GraphQL XHRs (URL, method, body,
  response), and saves fixtures to `data/madlan_fixtures/`. Runs from a residential IP or via `MADLAN_PROXY`. Its output is the
  input needed to finalize `madlan_parse.py`.

### T7 — HEADFUL real Chrome from the user's residential IP — **SUCCESS** ✅
Ran `scripts/madlan_probe.py` (headful, `channel="chrome"`, persistent profile, homepage warm-up)
on the user's Mac. Both pages rendered **HTTP 200** (search 380 KB, item 2.5 MB) — no CAPTCHA needed.
Confirms: (a) a *headless* browser is fingerprint-flagged by PX even on a residential IP, but a
*headful real-Chrome* passes; (b) production must run headful from a residential connection, like Yad2.

Bug fixed during T7: the PX sensor script (`_pxAppId`, `client.px-cloud.net`) is present on EVERY
Madlan page including good ones, so block detection keys on HTTP 403/429 + the captcha widget, and
short-circuits to "not blocked" whenever the SSR blob is present.

## Data shape (reverse-engineered from the T7 fixtures)
Madlan is a `@loadable` React app; it embeds Redux/Apollo hydration state in
`<script>window.__SSR_HYDRATED_CONTEXT__={…}</script>` (NOT `__NEXT_DATA__`). The blob is a **JS
object literal, not strict JSON** — it has bare `undefined` value tokens (neutralise before `json.loads`).

Inside `reduxInitialState.domainData` (Apollo-style cache, keyed by query name, each `{data, loading, networkStatus, …}`):
- **search** → `searchList.data.searchPoiV2` = `{ total, cursor, poi:[ …15 listings… ] }`
- **item**   → `bulletinsByIds.data.poiByIds[0]`

Each `poi` (same shape on both; item has extra detail): `id`, `locationPoint.{lat,lng}`,
`addressDetails.{city,neighbourhood,streetName,streetNumber}`, `price`, `beds` (rooms), `area` (m²),
`floor`, `floors`, `parking`, `generalCondition`, `buildingClass`, `monthlyTaxes`, `commonCharges`,
`availableDate`, `firstTimeSeen`, `images[].imageUrl`, `virtualTours`, `poc` (agent), and
`amenities.{elevator, airConditioner, secureRoom(=ממ"ד), miklat(=shelter), mamak, balcony,
julietBalcony, additionalAreas.balconyAreas, sunBoiler, isFurnished, unitPetsAllowed, garage, …}`.
The search-filter amenity tokens (`secureRoom,mamak,miklat,balcony,elevator`) ARE these field names.

Images: `imageUrl` is host-relative; the raw path 302-redirects, so prefix
`https://images2.madlan.co.il/t:nonce:v=5;convert:type=webp` (from the page's ld+json) → HTTP 200 webp.
The image CDN is **not** behind PX (downloads with plain `requests`, like Yad2's img CDN).

## Modules delivered (all mirror the Yad2 architecture)
- `scripts/madlan_parse.py` — pure parser: `extract_ssr_context` / `extract_feed_listings` /
  `extract_item_detail` / `parse_listing` → the SAME schema `yad2_parse` emits, plus `source="madlan"`.
  Verified against the real fixtures (`tests/test_madlan.py`, `python scripts/madlan_parse.py`).
- `scripts/madlan_fetch.py` — `MadlanSession`: headful real-Chrome + **persistent profile**
  (`data/.madlan_profile`) so the PX-clearing cookie survives runs; `MADLAN_PROXY` supported.
- `scripts/madlan_scraper.py` — orchestrator: search URL(s) → parsed rows (optionally enriched from
  item pages) → deduped DataFrame. `config/madlan_searches.py` holds the search URLs.
- `utils/dedup.py` — cross-source dedup (geo ≤40 m + rooms + price; street/city fallback) +
  `combine_and_dedupe([yad2_df, madlan_df])`. Same physical flat on both sites → one dup group.
- `scripts/run_all_sources.py` — combined entry point: Yad2 + Madlan → dedupe → Sheets upsert +
  gallery + Madlan-only Telegram notifications. Leaves `main.py` (Yad2-only) untouched.

## How to run (on a residential machine)
```bash
# Madlan only (opens a Chrome window; solve the PX challenge once if shown):
python scripts/madlan_scraper.py                 # -> data/madlan_listings.csv

# Both sources + cross-source dedup + Sheets + gallery + Madlan-only notifications:
python scripts/run_all_sources.py                # the multi-source entry point
```
`run_all_sources.py` is the combined counterpart of `main.py` (which stays Yad2-only) — point your
launchd/cron at it to include Madlan. Cron tip: warm `data/.madlan_profile` once with
`MADLAN_HEADFUL=1`, then headless runs reuse the PX-cleared cookie.

Dedup in code: `from utils.dedup import combine_and_dedupe; combine_and_dedupe([yad2_df, madlan_df])`
(Yad2 rows need `source="yad2"`; the runner tags them). `combined[combined.is_primary]` = one row per
physical property; `dup_sources == ["yad2","madlan"]` marks a flat listed on both.

## Pagination
Madlan pages results via offset-cursor **GraphQL** calls (`searchPoiV2.cursor.bulletinsOffset`,
`limit:50/offset`), NOT URL `?page=`. `MadlanSession.fetch_search` scrolls the search page to trigger
those `/api2` calls and collects the extra `searchPoiV2` pois beyond the ~15 the SSR embeds
(`MADLAN_MAX_RESULTS`, default 200). It degrades to SSR-only if scrolling loads nothing, so it never
returns *fewer* than page 1. **Unverified from this datacenter IP (PX-blocked) — verify the scroll
reaches all pages on a residential run.** The reference Herzliya search has `total:15`, fully covered
by the SSR page, so pagination is exercised only by broader searches.

## Notes / next steps
- Detail enrichment (`MADLAN_FETCH_DETAILS`) defaults **on** and must stay on: the search feed has
  no `amenities` object, so feed-only rows report elevator/mamad/shelter/AC as null — which the
  notifier renders as "No" (a real elevator shown as "no elevator"). Each listing is enriched from
  its item page (one extra fetch per listing). Set it off only if you truly don't need amenities.
- `run_all_sources.py` notifies only Madlan listings NOT also on Yad2 (cross-source dups were already
  announced by the Yad2 run) — the concrete payoff of the dedup step.
- **Nearby-city filtering**: Madlan's search feed pads results with adjacent-city listings
  (`searchPoiV2.totalNearby` > 0 — a Herzliya search also returned רמת השרון / רעננה flats, which
  triggered a false notification). The scraper now keeps only listings whose `addressDetails.cityDocId`
  matches the search URL's area slug (e.g. `הרצליה-ישראל`); override per-search with `city_doc_id` in
  `config/madlan_searches.py`.



