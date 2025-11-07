# ⏰ Israel Time-Based Schedule Configuration

This document explains how the workflow is configured to run **every 30 minutes** but **only between 07:00-23:00 Israel time**.

## 🎯 Current Configuration

The workflow now runs every 30 minutes and automatically checks if the current time in Israel is within your desired window (07:00-23:00).

### ✅ What Happens

**During operating hours (07:00-23:00 Israel time)**:
- ✅ Workflow runs normally
- ✅ Scrapes Yad2 listings
- ✅ Updates Google Sheets
- ✅ Sends notifications

**Outside operating hours (23:00-07:00 Israel time)**:
- ⏸️ Workflow checks time and skips execution
- ⏸️ No scraping happens
- ⏸️ Minimal resource usage (just the time check)
- ⏸️ Workflow shows as "skipped" in GitHub Actions

## 🌍 Timezone Handling

**Automatic Daylight Saving Time (DST) Support**:
- ✅ Uses `Asia/Jerusalem` timezone
- ✅ Automatically handles IST (UTC+2) in winter
- ✅ Automatically handles IDT (UTC+3) in summer
- ✅ No manual adjustments needed!

**Israel DST Schedule**:
- **Spring Forward**: Last Friday before April 2nd (UTC+3)
- **Fall Back**: Last Sunday before October 26th (UTC+2)

## 📊 Schedule Details

| Setting | Value |
|---------|-------|
| **Cron Schedule** | `*/30 * * * *` (every 30 minutes) |
| **Active Hours** | 07:00-23:00 Israel time |
| **Runs per day** | ~32 runs (16 hours × 2 per hour) |
| **Timezone** | Asia/Jerusalem (auto DST) |

### Example Schedule

```
Israel Time    Status
06:30         ⏸️ Skipped
07:00         ✅ Runs
07:30         ✅ Runs
08:00         ✅ Runs
...
22:30         ✅ Runs
23:00         ⏸️ Skipped
23:30         ⏸️ Skipped
00:00         ⏸️ Skipped
```

## 🔧 How It Works

The workflow includes a time check step that:

1. **Gets current Israel time**: Uses `TZ='Asia/Jerusalem'`
2. **Extracts the hour**: Checks if hour is between 7 and 22 (inclusive)
3. **Sets a flag**: `should_run=true` or `should_run=false`
4. **Controls all steps**: All subsequent steps check this flag

```bash
# Time check logic
if [ $ISRAEL_HOUR -ge 7 ] && [ $ISRAEL_HOUR -lt 23 ]; then
  # Run the workflow
else
  # Skip the workflow
fi
```

## ⚙️ Alternative Approaches

If you want to modify the schedule, here are other options:

### Option 1: Pure Cron (Manual DST Management)

**Winter (IST - UTC+2)**:
```yaml
on:
  schedule:
    # 07:00-23:00 IST = 05:00-21:00 UTC
    - cron: '0,30 5-21 * * *'    # Every 30 min from 05:00-21:59 UTC
    - cron: '0 22 * * *'          # Also at 22:00 UTC (last run at 00:00 IST)
```

**Summer (IDT - UTC+3)**:
```yaml
on:
  schedule:
    # 07:00-23:00 IDT = 04:00-20:00 UTC
    - cron: '0,30 4-20 * * *'    # Every 30 min from 04:00-20:59 UTC
    - cron: '0 21 * * *'          # Also at 21:00 UTC (last run at 00:00 IDT)
```

**❌ Cons**: You must manually update the workflow twice a year for DST changes.

### Option 2: Current Smart Time Check (Recommended)

**Current implementation**:
```yaml
on:
  schedule:
    - cron: '*/30 * * * *'  # Run every 30 min, time filtering in workflow
```

**✅ Pros**:
- Automatic DST handling
- Easy to modify hours
- No manual updates needed
- Clear logging in Actions

**⚠️ Minor Con**: Workflow still triggers every 30 minutes but exits early when outside hours (uses ~5 seconds of compute time per skipped run)

### Option 3: Two Separate Schedules for DST

```yaml
on:
  schedule:
    # Winter schedule (October-March): UTC+2
    - cron: '0,30 5-21 * 10-12,1-3 *'  # Oct-Mar
    - cron: '0 22 10-12,1-3 * *'

    # Summer schedule (April-September): UTC+3
    - cron: '0,30 4-20 * 4-9 *'        # Apr-Sep
    - cron: '0 21 4-9 * *'
```

**⚠️ Cons**: Approximates DST dates (Israel DST doesn't follow month boundaries exactly)

## 🎛️ Customizing Your Hours

To change the operating hours, modify the time check in `.github/workflows/scraper.yml`:

```bash
# Current: 07:00-23:00
if [ $ISRAEL_HOUR -ge 7 ] && [ $ISRAEL_HOUR -lt 23 ]; then

# Example: 08:00-22:00
if [ $ISRAEL_HOUR -ge 8 ] && [ $ISRAEL_HOUR -lt 22 ]; then

# Example: 06:00-midnight
if [ $ISRAEL_HOUR -ge 6 ] && [ $ISRAEL_HOUR -lt 24 ]; then

# Example: 09:00-17:00 (business hours only)
if [ $ISRAEL_HOUR -ge 9 ] && [ $ISRAEL_HOUR -lt 17 ]; then
```

## 🧪 Testing Your Schedule

### Test Time Check Locally

```bash
# Check current Israel time
TZ='Asia/Jerusalem' date

# Test the hour extraction
TZ='Asia/Jerusalem' date +%H

# Test the condition
ISRAEL_HOUR=$(TZ='Asia/Jerusalem' date +%H)
if [ $ISRAEL_HOUR -ge 7 ] && [ $ISRAEL_HOUR -lt 23 ]; then
  echo "Would run now"
else
  echo "Would skip now"
fi
```

### Test on GitHub Actions

1. **Manual trigger**: Actions → Yad2 Real Estate Scraper → Run workflow
2. **Check logs**: Look for "Check Israel time window" step
3. **Verify output**:
   - ✅ "Within operating hours" → Workflow runs
   - ⏸️ "Outside operating hours" → Workflow skips

## 📊 Monitoring

### View Skipped Runs

In the GitHub Actions interface:
- **Skipped runs** will show as successful (green) but very fast (~5-10 seconds)
- Look at the first step "Check Israel time window" to see the actual time
- Successful scrapes will take 1-2 minutes

### Expected Patterns

**Typical day**:
```
00:00 ⏸️ (5s)
00:30 ⏸️ (5s)
...
06:30 ⏸️ (5s)
07:00 ✅ (90s) ← First run of the day
07:30 ✅ (90s)
...
22:30 ✅ (90s) ← Last run of the day
23:00 ⏸️ (5s)
23:30 ⏸️ (5s)
```

## 💰 Cost Considerations

### Current Setup (Smart Time Check)
- **Runs triggered**: 48/day (every 30 minutes)
- **Actual scrapes**: ~32/day (only during 07:00-23:00)
- **Skipped checks**: ~16/day (5 seconds each = ~80 seconds total)
- **Total minutes/month**: ~1,440 minutes (actual scraping) + ~40 minutes (time checks) = **~1,480 minutes/month**

### With Pure Cron (No Skipped Runs)
- **Runs triggered**: 32/day
- **Total minutes/month**: ~1,440 minutes

**Difference**: ~40 minutes/month for automatic DST handling and flexibility

### Recommendation
✅ **Current smart time check is recommended** because:
- Extra 40 minutes/month is negligible
- Automatic DST handling
- Easy to modify hours
- Better logging and visibility

## 🔔 Notifications During Off-Hours

If you manually trigger the workflow outside 07:00-23:00:
- ⏸️ Workflow will skip (respects the time window)
- 💡 To force a run outside hours, temporarily comment out the time check

## 📝 Summary

Your workflow is now configured to:
- ✅ Run every 30 minutes automatically
- ✅ Only execute between 07:00-23:00 Israel time
- ✅ Automatically handle daylight saving time
- ✅ Skip gracefully outside operating hours
- ✅ Provide clear logging of when it runs vs skips

**No manual intervention needed!** The workflow will adapt to DST changes automatically.

---

**Questions or need to modify the schedule? Edit `.github/workflows/scraper.yml` and adjust the time check condition!**
