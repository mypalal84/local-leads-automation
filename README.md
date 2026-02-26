# ⚡️ ZBA Digital — Local Leads Automation 🔥

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Automation](https://img.shields.io/badge/Automation-Daily-green)
![Email](https://img.shields.io/badge/Email-Gmail-orange)
![APIs](https://img.shields.io/badge/APIs-Serper%20%7C%20Hunter-purple)
![Status](https://img.shields.io/badge/Status-Active-success)

## 🧭 Overview

ZBA Digital’s Daily Leads Pipeline automatically finds local small-business owners who don’t have modern websites, verifies their contact emails, and sends personalized cold emails with a configurable daily cap.

## 🧱 End-to-End Flow

- 🔍 Discover new local business leads (via Serper API)
- ✉️ Verify emails (Hunter.io), bounded by remaining daily quota
- 🤖 Send personalized cold emails with rotating subject lines
- 🛑 Enforce daily send limits and suppression list checks
- 📬 Track replies in Gmail and auto-notify you

Everything runs from your local cron scheduler each morning.

## 🗂 Project Structure

```text
Daily_Leads/
├── .env                         # API keys, Gmail app password, environment variables
│
├── logs/                        # Log outputs
│   ├── summary.log              # Lead generation logs (per city/service)
│   ├── email.log                # Sent emails + detected replies
│   ├── daily_kpi.csv            # Daily KPI snapshots per pipeline run
│   ├── run_metrics_<timestamp>.json # Per-run API call counters
│   ├── pipeline.log             # Master cron execution log
│   └── .pairs.tmp               # Auto‑generated, then removed
│
├── data/                        # Lead and contact data
│   ├── leads_<city>_<service>_NO_WEBSITE_<date>.csv
│   ├── daily_sent_<date>.csv    # Running sent count used for daily cap
│   ├── sent_log.csv             # Prevent re‑sending to same address
│   ├── replies.csv              # Stores detected replies
│   ├── suppressions.csv         # Never-send list (manual + auto-suppressed)
│   ├── cache/                   # Cached Serper/Hunter responses (TTL-pruned)
│   └── archive/                 # Archived lead CSV snapshots
│
├── src/
│   ├── master_daily_pipeline.sh # 🚀 Main orchestrator (cron entry point)
│   ├── discover_no_website_leads.py # Lead discovery (Serper)
│   ├── find_no_website_emails.py# Lead enrichment (Serper + Hunter)
│   ├── send_cold_emails.py      # Outreach + reply handling
│   └── daily_summary_report.py  # Optional standalone summary mailer
│
├── tests/                       # Pytest suite (unit + dry-run integration)
│
└── .github/workflows/
    └── tests.yml                # CI: run pytest on push/PR

archive/                         # Archived legacy scripts (safe to delete later)
    ├── auto_daily_pipeline.py
    ├── run_pipeline.sh
    ├── daily_report_emailer.py
    ├── lead_generator_email.py
    └── filter_no_website.py                               # 🔑 environment variables
```

## ⚙️ Environment Setup 🔧

Create a file named `.env` in your project root directory:

```env
# Gmail credentials (use App Passwords!)
DAILY_LEAD_EMAIL_SENDER=yourname@gmail.com
DAILY_LEAD_EMAIL_PASS=your_app_specific_password
REPLY_NOTIFY_TO="your_notification_address@gmail.com"

# Pipeline controls
DAILY_EMAIL_TARGET=50
ENRICH_BUFFER_MULTIPLIER=2
EXPECTED_SENDS_PER_PAIR=5
MAX_PAIRS_PER_RUN=15
LEAD_SCORE_THRESHOLD=2
CACHE_TTL_DAYS=7

# Optional footer appended to cold emails
UNSUBSCRIBE_FOOTER="If you'd prefer not to hear from me again, reply STOP and I will remove you immediately."

# API connections
SERPER_API_KEY=your_serper_key
HUNTER_API_KEY=your_hunter_key
```

🧠 Tip: If you use 2-Factor Auth with Gmail, generate an App Password here: https://myaccount.google.com/apppasswords

## 📆 Automated Daily Schedule 🕒

Example cron jobs (macOS / Linux):

```bash
0 7 * * * /Users/alexcahn/Scripts/Daily_Leads/src/master_daily_pipeline.sh >> /Users/alexcahn/Scripts/Daily_Leads/logs/pipeline.log 2>&1
```

✅ Fully hands-off once scheduled.

### Dry-run (safe test mode)

Run the full control flow without API calls or sending emails:

```bash
cd /Users/alexcahn/Scripts/Daily_Leads/src
DRY_RUN=true PIPELINE_DELAY_BETWEEN_RUNS=1 ./master_daily_pipeline.sh
```

### Recommended production run flags

```bash
cd /Users/alexcahn/Scripts/Daily_Leads/src
DAILY_EMAIL_TARGET=50 ENRICH_BUFFER_MULTIPLIER=2 ./master_daily_pipeline.sh
```

## 📨 Cold Email Template

```text
Hi {{business}},

I came across {{business}} while checking {{service}} providers in {{town}}.
I help local owners like you launch professional, mobile-friendly websites that attract more calls — within 7 days.

Is this something you’d be open to exploring for {{business}}?

Best,
Alex
ZBA Digital
www.zbadigital.com
```

## 🎯 Smart Features

- 💡 Dynamic tokens: `business`, `town`, `service` auto-filled per lead
- 🎲 Rotating subject lines for A/B testing
- ⏳ Random send delay (1-5 seconds) for human-like pacing
- 🎯 Daily send cap enforcement via `DAILY_EMAIL_TARGET`
- 💸 Quota-aware enrichment to reduce API usage (`ENRICH_BUFFER_MULTIPLIER`)
- 📊 Dynamic pair scheduling (`EXPECTED_SENDS_PER_PAIR`, `MAX_PAIRS_PER_RUN`)
- ✅ Lead quality gate before send (`LEAD_SCORE_THRESHOLD`)
- ♻️ Serper/Hunter cache with TTL pruning (`CACHE_TTL_DAYS`)
- 🛑 Suppression list enforcement (`data/suppressions.csv`)
- 📬 Unsubscribe footer support via `UNSUBSCRIBE_FOOTER`
- 🔁 Reply tracking and notifications
- 📈 Daily KPI snapshots written to `logs/daily_kpi.csv`
- 🔢 Run-level API call totals (Google Places / Serper / Hunter) included in summary email

## 📬 Reply Tracking & Notifications

Inbound replies are automatically processed through Gmail IMAP:

| Step | Action |
| --- | --- |
| 🧾 1 | Parse INBOX for replies from the past 7 days |
| 📓 2 | Log sender, subject, and snippet to `data/replies.csv` |
| 🧹 3 | Remove those addresses from `data/sent_log.csv` |
| 🚫 4 | Auto-add negative replies (unsubscribe/stop/not interested) to `data/suppressions.csv` |
| 📧 5 | Send a notification email with a concise summary |

Example email notification:

```text
Subject: [Pipeline] 2 new replies

New replies detected:

- john@evergreenhvac.com | Re: Quick question about Evergreen HVAC | "Hi Alex, let’s chat next week about pricing."...
- info@blueflame.com | Re: Website for Blue Flame Heating? | "Sure — send me some examples!"...

Total replied addresses: 2
```

## 🧠 Core Scripts

| Script | Description |
| --- | --- |
| `discover_no_website_leads.py` | 🔎 Finds likely no-website leads and writes `leads_<city>_<service>_NO_WEBSITE_<date>.csv`. |
| `find_no_website_emails.py` | 🔍 Enriches discovery output, re-checks live websites, and verifies contact emails via Serper and Hunter APIs. |
| `send_cold_emails.py` | ✉️ Sends cold emails using dynamic fields, rotating subject lines, and reply processing (auto-cleanup + notifications). |
| `daily_summary_report.py` | 📊 Generates a daily overview of lead counts and campaign performance. |

## 🗃 Data Outputs 📑

| File / Folder | Description |
| --- | --- |
| `data/leads_<city>_<service>_NO_WEBSITE_<date>.csv` | Discovery/enrichment output used by outreach |
| `data/daily_sent_<date>.csv` | Daily send ledger used to enforce email caps |
| `data/sent_log.csv` | Rolling record of all recipients already emailed |
| `data/replies.csv` | Archived reply summaries (sender, subject, snippet, date) |
| `data/suppressions.csv` | Suppressed addresses (manual and auto from negative replies) |
| `data/cache/` | Cached API responses used to reduce repeat Serper/Hunter calls |
| `logs/daily_kpi.csv` | Run-by-run KPIs: pairs, sent, replies, quota remaining |
| `logs/run_metrics_<timestamp>.json` | Per-run API counters used in summary email |
| `logs/` | Process and cron output logs |

## ✅ Testing

Run the test suite:

```bash
cd /Users/alexcahn/Scripts/Daily_Leads
/Users/alexcahn/Scripts/.venv/bin/python -m pytest
```

The suite includes:

- Unit tests for sender, enrichment, discovery, and summary modules
- Parameterized edge-case tests for filename and parsing behavior
- Dry-run integration validation of master pipeline KPI output

CI runs the same suite on push and pull request via `.github/workflows/tests.yml`.

## 🛡 Best Practices

- ✨ Use App Passwords and enable Gmail IMAP
- 📦 Rotate API keys every 90 days (Serper / Hunter)
- 🗂 Archive old logs monthly
- 🚫 To pause outreach, comment out the second cron job

```bash
# pause cold emails
# 30 7 * * * cd ~/Scripts/Daily_Leads/src ... send_cold_emails.py
```

## 🧾 Version History 📅

| Date | Update |
| --- | --- |
| 2026-02-22 | Added subject rotation, random send delays, Gmail reply processing, automatic cleanup, and reply notification emails. |
| 2026-02-26 | Added dry-run mode, filename consistency fixes, and summary metric corrections. |
| 2026-02-26 | Added daily send cap, quota-aware enrichment, suppression list support, and KPI logging. |
| 2026-02-26 | Added pytest suite with unit and dry-run integration coverage. |
| 2026-02-26 | Added dynamic pair scheduling, lead scoring, API caching/pruning, CI workflow, and API-call totals in summary email. |

---

❤️ Built by Alex Cahn / ZBA Digital — streamlining local lead generation through automation.

