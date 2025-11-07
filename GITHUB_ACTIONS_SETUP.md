# GitHub Actions Setup Guide

This guide will help you set up automated scraping on GitHub Actions that runs every 30 minutes while still maintaining the ability to run locally.

## 🎯 Overview

The GitHub Actions workflow will:
- ✅ Run automatically every 30 minutes
- ✅ Scrape Yad2 listings using your configured searches
- ✅ Update your Google Sheets automatically
- ✅ Send Telegram notifications for new properties
- ✅ Maintain state between runs (seen properties database)
- ✅ Allow local execution without any changes

## 📋 Prerequisites

Before setting up GitHub Actions, ensure you have:
1. A GitHub account and repository for this project
2. Google Sheets API credentials (service account JSON)
3. A Google Sheet with appropriate permissions
4. (Optional) Telegram bot token and chat ID

## 🚀 Setup Steps

### Step 1: Push Your Code to GitHub

```bash
# Initialize git if not already done
git init

# Add your files
git add .

# Commit your changes
git commit -m "Initial commit - Yad2 scraper"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push to GitHub
git push -u origin main
```

**⚠️ IMPORTANT**: Make sure your `.env` file and `config/credentials.json` are NOT committed! They should already be in `.gitignore`.

### Step 2: Set Up GitHub Secrets

Go to your GitHub repository settings and add the following secrets:

**Settings → Secrets and variables → Actions → New repository secret**

#### Required Secrets

| Secret Name | Description | Example/How to Get |
|------------|-------------|-------------------|
| `GOOGLE_CREDENTIALS_JSON` | **Your entire Google Service Account JSON file** | Copy the entire contents of `config/credentials.json` |
| `SPREADSHEET_NAME` | Name of your Google Sheet | `Yad2 Properties` |
| `WORKSHEET_NAME` | Name of the worksheet/tab | `Properties` |
| `SPREADSHEET_ID` | Google Sheets ID from URL | Copy from URL: `https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit` |

#### Optional Secrets (Telegram Notifications)

| Secret Name | Description | Example |
|------------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID | `123456789` |
| `ENABLE_NOTIFICATIONS` | Enable all notifications | `true` or `false` |
| `NOTIFY_ON_NEW_PROPERTIES` | Notify for new properties | `true` or `false` |
| `NOTIFY_ON_ERROR` | Notify on errors | `true` or `false` |

#### Optional Configuration

| Secret Name | Description | Default |
|------------|-------------|---------|
| `REQUEST_DELAY` | Delay between requests (seconds) | `1.0` |

### Step 3: Setting Up Google Credentials Secret

The `GOOGLE_CREDENTIALS_JSON` secret is the most important. Here's exactly how to set it up:

1. **Open your local `config/credentials.json` file**
2. **Copy the ENTIRE contents** (it should look like this):
   ```json
   {
     "type": "service_account",
     "project_id": "your-project-123456",
     "private_key_id": "abc123...",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
     "client_id": "123456789",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
     "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
   }
   ```
3. **Go to GitHub**: Your Repo → Settings → Secrets and variables → Actions
4. **Click "New repository secret"**
5. **Name**: `GOOGLE_CREDENTIALS_JSON`
6. **Value**: Paste the entire JSON contents
7. **Click "Add secret"**

### Step 4: Verify Google Sheets Permissions

Make sure your Google Sheet is shared with the service account email:

1. Open your Google Sheet
2. Click **Share** button (top right)
3. Add the service account email from `credentials.json` (`client_email` field)
4. Give it **Editor** permissions
5. Uncheck "Notify people" (it's a bot, not a person)
6. Click **Share**

### Step 5: Enable GitHub Actions

1. Go to your repository on GitHub
2. Click the **Actions** tab
3. If prompted, click **"I understand my workflows, go ahead and enable them"**
4. You should see the workflow: **"Yad2 Real Estate Scraper"**

### Step 6: Test the Workflow

#### Option A: Manual Test (Recommended First)

1. Go to **Actions** tab
2. Click on **"Yad2 Real Estate Scraper"** workflow
3. Click **"Run workflow"** dropdown (right side)
4. Click the green **"Run workflow"** button
5. Watch it run in real-time!

#### Option B: Wait for Scheduled Run

The workflow will automatically run every 30 minutes. The first run will be at the next half-hour mark (e.g., 10:00, 10:30, 11:00, etc.)

## 📊 Monitoring Your Workflow

### View Workflow Runs

1. Go to **Actions** tab in your repository
2. Click on any workflow run to see details
3. Click on the **"scrape"** job to see detailed logs
4. Expand each step to see what happened

### Successful Run Indicators

✅ Green checkmark next to the workflow run
✅ "Update complete!" message in logs
✅ Your Google Sheet is updated
✅ Telegram notifications received (if configured)

### Understanding the Workflow Status

- 🟢 **Green**: Workflow completed successfully
- 🟡 **Yellow**: Workflow is currently running
- 🔴 **Red**: Workflow failed (check logs for errors)
- ⚪ **Gray**: Workflow is queued or disabled

## 🔧 Customizing the Schedule

### Current Configuration: Israel Time-Based Schedule

The workflow is configured to run **every 30 minutes** but **only between 07:00-23:00 Israel time**.

**📖 See detailed guide**: [ISRAEL_TIME_SCHEDULE.md](ISRAEL_TIME_SCHEDULE.md)

**How it works**:
- ✅ Automatically checks Israel time (Asia/Jerusalem timezone)
- ✅ Handles daylight saving time automatically
- ✅ Runs ~32 times per day (only during active hours)
- ✅ Skips gracefully outside 07:00-23:00

**To change the hours**, edit the time check in `.github/workflows/scraper.yml`:
```bash
# Change these numbers to your desired hours
if [ $ISRAEL_HOUR -ge 7 ] && [ $ISRAEL_HOUR -lt 23 ]; then
```

### Alternative: Basic Cron Schedules

To change how often the scraper runs, edit `.github/workflows/scraper.yml`:

```yaml
on:
  schedule:
    - cron: '*/30 * * * *'  # Every 30 minutes (current)
```

**Common Schedule Examples:**

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Every 15 minutes | `*/15 * * * *` | Runs 96 times per day |
| Every 30 minutes | `*/30 * * * *` | Runs 48 times per day |
| Every hour | `0 * * * *` | Runs 24 times per day |
| Every 2 hours | `0 */2 * * *` | Runs 12 times per day |
| Every day at 9 AM | `0 9 * * *` | Runs once per day at 9:00 AM UTC |
| Every weekday at 9 AM | `0 9 * * 1-5` | Runs Mon-Fri at 9:00 AM UTC |

**⏰ Important**: Basic cron schedules use UTC time zone! For Israel-specific times, see [ISRAEL_TIME_SCHEDULE.md](ISRAEL_TIME_SCHEDULE.md).

### Cron Expression Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
* * * * *
```

## 🏠 Running Locally

**Good news**: Your local setup still works exactly the same way!

```bash
# Make sure you're in your virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run the scraper
python scripts/main.py
```

The workflow uses **GitHub Secrets** while local execution uses your **`.env` file** and **`config/credentials.json`**.

## 🐛 Troubleshooting

### Common Issues and Solutions

#### 1. Workflow Fails with "Authentication Error"

**Problem**: Google Sheets authentication failed

**Solutions**:
- ✅ Verify `GOOGLE_CREDENTIALS_JSON` secret is set correctly
- ✅ Copy the ENTIRE contents of `credentials.json` (including all newlines in the private key)
- ✅ Make sure the Google Sheet is shared with the service account email
- ✅ Check if `SPREADSHEET_ID` matches your actual Google Sheet ID

#### 2. Workflow Runs but No Data is Updated

**Problem**: Scraper runs successfully but Google Sheet isn't updated

**Solutions**:
- ✅ Check if `SPREADSHEET_NAME` exactly matches your Google Sheet name (case-sensitive!)
- ✅ Check if `WORKSHEET_NAME` exactly matches your worksheet tab name
- ✅ Verify the service account has **Editor** permissions (not just Viewer)

#### 3. "No Listings Found" Message

**Problem**: Scraper runs but finds no properties

**Solutions**:
- ✅ Check if your search parameters in `config/search_configs.py` are too restrictive
- ✅ Verify Yad2 website is accessible
- ✅ Test the same search manually on Yad2.co.il to see if listings exist

#### 4. Telegram Notifications Not Working

**Problem**: Script runs but no Telegram messages received

**Solutions**:
- ✅ Verify `TELEGRAM_BOT_TOKEN` is correct
- ✅ Verify `TELEGRAM_CHAT_ID` is correct
- ✅ Set `ENABLE_NOTIFICATIONS=true` and `NOTIFY_ON_NEW_PROPERTIES=true`
- ✅ Check if the bot is blocked or chat is deleted
- ✅ Test your bot manually: `https://api.telegram.org/bot<TOKEN>/getMe`

#### 5. Workflow Not Running on Schedule

**Problem**: Manual runs work, but scheduled runs don't happen

**Solutions**:
- ✅ Make sure the workflow file is on the **main** branch (or your default branch)
- ✅ GitHub Actions requires at least one successful workflow run to enable scheduling
- ✅ Check Actions tab: Is the workflow enabled? (not disabled)
- ✅ Note: GitHub Actions scheduled workflows may have a **5-10 minute delay**

#### 6. "Resource not accessible by integration"

**Problem**: Workflow can't access repository or cache

**Solutions**:
- ✅ Go to Settings → Actions → General → Workflow permissions
- ✅ Select "Read and write permissions"
- ✅ Check "Allow GitHub Actions to create and approve pull requests"
- ✅ Click **Save**

### Viewing Detailed Logs

1. Go to **Actions** tab
2. Click on the failed workflow run
3. Click on the **"scrape"** job
4. Expand the failed step to see detailed error messages
5. Look for Python tracebacks and error messages

### Testing Secrets Locally

To verify your secrets are formatted correctly, you can test them locally:

```bash
# Create a temporary test file
cat > test_creds.json << 'EOF'
<paste your GOOGLE_CREDENTIALS_JSON secret here>
EOF

# Verify it's valid JSON
python3 -c "import json; json.load(open('test_creds.json'))"

# Clean up
rm test_creds.json
```

If the command completes without error, your JSON is valid!

## 📈 Usage Limits & Best Practices

### GitHub Actions Limits

**Free tier** (Public repositories):
- ✅ Unlimited minutes for public repos
- ✅ 500 MB storage for artifacts

**Free tier** (Private repositories):
- ⚠️ 2,000 minutes per month
- ⚠️ 500 MB storage for artifacts

**Running every 30 minutes**:
- Each run takes ~1-2 minutes
- 48 runs/day × 30 days = 1,440 runs/month
- Estimated usage: ~1,440-2,880 minutes/month

**💡 Tip**: Use a **public repository** for unlimited runs!

### Rate Limiting Best Practices

1. **Don't run too frequently**: Every 30 minutes is reasonable
2. **Use `REQUEST_DELAY`**: Add delays between API requests (default: 1 second)
3. **Respect Yad2's Terms of Service**: Be a good internet citizen
4. **Monitor your usage**: Check Actions tab regularly

## 🔒 Security Best Practices

### ✅ DO

- ✅ Use GitHub Secrets for all sensitive data
- ✅ Keep your repository private if it contains proprietary search configs
- ✅ Regularly rotate your Telegram bot token
- ✅ Monitor workflow runs for suspicious activity
- ✅ Use `workflow_dispatch` for manual testing before enabling schedule

### ❌ DON'T

- ❌ Never commit `.env` or `credentials.json`
- ❌ Never print secrets in workflow logs
- ❌ Never share your repository with untrusted users if it's private
- ❌ Never commit sensitive search parameters that reveal your apartment hunting strategy 😉

## 🎓 Advanced Configuration

### Running in Multiple Time Zones

If you want to scrape at specific times in your local timezone:

```yaml
# Example: Run every day at 9 AM Israel Time (7 AM UTC in summer, 6 AM UTC in winter)
# Note: Adjust for daylight saving time
on:
  schedule:
    - cron: '0 6 * * *'  # Winter time (UTC+2)
    - cron: '0 7 * * *'  # Summer time (UTC+3)
```

### Conditional Telegram Notifications

Want notifications only during certain hours? Modify the workflow:

```yaml
- name: Check time for notifications
  id: check_time
  run: |
    hour=$(date -u +%H)
    if [ $hour -ge 6 ] && [ $hour -le 22 ]; then
      echo "send_notifications=true" >> $GITHUB_OUTPUT
    else
      echo "send_notifications=false" >> $GITHUB_OUTPUT
    fi

- name: Run scraper
  env:
    NOTIFY_ON_NEW_PROPERTIES: ${{ steps.check_time.outputs.send_notifications }}
  run: python scripts/main.py
```

### Adding Workflow Notifications

Get notified when workflows fail:

1. Watch your repository: Click "Watch" → "Custom" → Check "Actions"
2. Enable email notifications: Settings → Notifications → Actions
3. Use Telegram for workflow status: Add to workflow:

```yaml
- name: Notify on failure
  if: failure()
  run: |
    curl -X POST "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
      -d "chat_id=${{ secrets.TELEGRAM_CHAT_ID }}" \
      -d "text=⚠️ Yad2 scraper workflow failed! Check: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

## 📞 Getting Help

If you encounter issues:

1. **Check the workflow logs** in the Actions tab
2. **Review this troubleshooting guide**
3. **Test locally first** to isolate the issue
4. **Check GitHub Actions status**: https://www.githubstatus.com/
5. **Verify all secrets are set correctly**

## ✅ Setup Checklist

Before enabling scheduled runs, verify:

- [ ] All required secrets are set in GitHub
- [ ] Google Sheets is shared with service account
- [ ] Manual workflow run succeeds
- [ ] Google Sheet is updated after manual run
- [ ] Telegram notifications work (if configured)
- [ ] `.env` and `credentials.json` are in `.gitignore`
- [ ] Workflow permissions are set to "Read and write"
- [ ] You understand the schedule and timezone (UTC)

## 🎉 Success!

Once everything is working:

✅ Your scraper runs automatically every 30 minutes
✅ Google Sheets stays updated with the latest listings
✅ You get instant Telegram notifications for new properties
✅ You can still run locally whenever you want
✅ Your apartment hunting is now fully automated! 🏠

---

**Happy apartment hunting! May you find your perfect home! 🏡**
