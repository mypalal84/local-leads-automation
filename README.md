# ⚡️ ZBA Digital — Local Leads Automation 🔥

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Automation](https://img.shields.io/badge/Automation-Daily-green)
![Email](https://img.shields.io/badge/Email-Gmail-orange)
![APIs](https://img.shields.io/badge/APIs-Serper%20%7C%20Hunter-purple)
![Status](https://img.shields.io/badge/Status-Active-success)

## 🧭 Overview

ZBA Digital’s Daily Leads Pipeline automatically finds local small-business owners who don’t have modern websites, verifies their contact emails, and sends one personalized cold email per day without manual intervention.

## 🧱 End-to-End Flow

- 🔍 Discover new local business leads (via Serper API)
- ✉️ Verify emails (Hunter.io)
- 🤖 Send personalized cold emails with rotating subject lines
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
│   ├── pipeline.log             # Master cron execution log
│   └── .pairs.tmp               # Auto‑generated, then removed
│
├── data/                        # Lead and contact data
│   ├── no_website_emails_<city>_<service>_<date>.csv
│   ├── sent_log.csv             # Prevent re‑sending to same address
│   ├── replies.csv              # Stores detected replies
│   └── archived/                # Optional backup folder for older CSVs
│
├── src/
│   ├── master_daily_pipeline.sh # 🚀 Main orchestrator (cron entry point)
│   ├── find_no_website_emails.py# Lead discovery (Serper + Hunter)
│   ├── send_cold_emails.py      # Outreach + reply handling
│   └── utils/                   # Optional helper scripts
│
└── archive/                     # Archived legacy scripts (safe to delete later)
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

# API connections
SERPER_API_KEY=your_serper_key
HUNTER_API_KEY=your_hunter_key
```

🧠 Tip: If you use 2-Factor Auth with Gmail, generate an App Password here: https://myaccount.google.com/apppasswords

## 📆 Automated Daily Schedule 🕒

Example cron jobs (macOS / Linux):

```bash 0 7 * * * /Users/alexcahn/Scripts/Daily_Leads/src/master_daily_pipeline.sh >> /Users/alexcahn/Scripts/Daily_Leads/logs/pipeline.log 2>&1
```

✅ Fully hands-off once scheduled.

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
- 🔁 Reply tracking and notifications

## 📬 Reply Tracking & Notifications

Inbound replies are automatically processed through Gmail IMAP:

| Step | Action |
| --- | --- |
| 🧾 1 | Parse INBOX for replies from the past 7 days |
| 📓 2 | Log sender, subject, and snippet to `data/replies.csv` |
| 🧹 3 | Remove those addresses from `data/sent_log.csv` |
| 📧 4 | Send a notification email with a concise summary |

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
| `find_no_website_emails.py` | 🔍 Discovers local businesses with no website / outdated website, then verifies emails via Serper and Hunter APIs. |
| `send_cold_emails.py` | ✉️ Sends cold emails using dynamic fields, rotating subject lines, and reply processing (auto-cleanup + notifications). |
| `daily_summary_report.py` | 📊 Generates a daily overview of lead counts and campaign performance. |

## 🗃 Data Outputs 📑

| File / Folder | Description |
| --- | --- |
| `data/no_website_emails_<town>_<service>_<date>.csv` | Verified contact list for that market segment |
| `data/sent_log.csv` | Rolling record of all recipients already emailed |
| `data/replies.csv` | Archived reply summaries (sender, subject, snippet, date) |
| `logs/` | Process and cron output logs |

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

---

❤️ Built by Alex Cahn / ZBA Digital — streamlining local lead generation through automation.

