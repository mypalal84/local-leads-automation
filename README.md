
⚡️ ZBA Digital — Local Leads Automation 🔥
Python
Automation
Email
APIs
Status

🧭 Overview
ZBA Digital’s Daily Leads Pipeline automatically finds local small‑business owners who don’t have modern websites, verifies their contact emails, and sends one personalized cold email per day — all without manual intervention.

🧱 End‑to‑End Flow:
🔍 Discover new local business leads (via Serper API)
✉️ Verify emails (Hunter.io)
🤖 Send personalized cold emails with rotating subject lines
📬 Track replies in Gmail and auto‑notify you
Everything runs from your local cron scheduler each morning.

🗂 Project Structure
code

/Scripts/Daily_Leads
│
├── src/
│   ├── find_no_website_emails.py      # 🔍 find & enrich new leads
│   ├── send_cold_emails.py            # ✉️ send cold emails + track replies
│   ├── daily_summary_report.py        # 🧾 generate activity summaries
│   └── utils/                         # helper functions (optional)
│
├── data/
│   ├── no_website_emails_<town>_<service>_<date>.csv   # verified leads
│   ├── sent_log.csv                  # all previously emailed contacts
│   ├── replies.csv                   # archived incoming replies
│   └── ...
│
├── logs/
│   ├── summary.log
│   └── email.log
│
└── .env                              # 🔑 environment variables
⚙️ Environment Setup 🔧
Create a file named .env in your project root directory:

env

# Gmail credentials (use App Passwords!)
DAILY_LEAD_EMAIL_SENDER=yourname@gmail.com
DAILY_LEAD_EMAIL_PASS=your_app_specific_password

# Fallback context (used only if filename parsing fails)
DEFAULT_SERVICE=website
DEFAULT_TOWN=Seattle

# API connections
SERPER_API_KEY=your_serper_key
HUNTER_API_KEY=your_hunter_key

# Notifications
REPLY_NOTIFY_TO=your_notification_email@domain.com
🧠 Tip: If you use 2‑Factor Auth with Gmail, generate an App Password here → https://myaccount.google.com/apppasswords

📆 Automated Daily Schedule 🕒
Example cronjobs (macOS / Linux):

bash

# 7:00 AM → Discover & verify new leads
0 7 * * * cd ~/Scripts/Daily_Leads/src && source ../.env \
  && /usr/bin/python3 find_no_website_emails.py hvac seattle >> ../logs/summary.log 2>&1

# 7:30 AM → Send cold emails + fetch replies
30 7 * * * cd ~/Scripts/Daily_Leads/src && source ../.env \
  && /usr/bin/python3 send_cold_emails.py >> ../logs/email.log 2>&1
✅ Fully hands‑off once scheduled!

📨 Cold Email Template
text

Hi {{business}},

I came across {{business}} while checking {{service}} providers in {{town}}.
I help local owners like you launch professional, mobile‑friendly websites that attract more calls — within 7 days.

Is this something you’d be open to exploring for {{business}}?

Best,
Alex
ZBA Digital
www.zbadigital.com
🎯 Smart Features
💡 Dynamic tokens → business, town, service auto‑filled per lead
🎲 Rotating subject lines for A/B testing (Quick question… | Website for… etc.)
⏳ Random send delay (1–5 seconds) for human‑like pacing
🔁 Reply Tracking & Notifications
📬 Inbound replies are automatically processed through Gmail IMAP:

Step	Action
🧾 1
Parse INBOX for replies from the past 7 days
📓 2
Log each sender, subject, and snippet → data/replies.csv
🧹 3
Remove those addresses from data/sent_log.csv
📧 4
Send you a notification email with a concise summary
Example Email Notification:

code

Subject: [Pipeline] 2 new replies

New replies detected:

- john@evergreenhvac.com | Re: Quick question about Evergreen HVAC | "Hi Alex, let’s chat next week about pricing."…
- info@blueflame.com | Re: Website for Blue Flame Heating? | "Sure – send me some examples!"…

Total replied addresses: 2
🧠 Core Scripts
Script	Description
find_no_website_emails.py
🔍 Discovers local businesses with no website / outdated website, verifies emails via Serper and Hunter APIs.
send_cold_emails.py
✉️ Sends cold emails using dynamic fields, random subject rotation, and logs replies (+ auto‑cleanup + notifications).
daily_summary_report.py
📊 Generates a daily overview of lead counts and campaign performance.
🗃 Data Outputs 📑
File / Folder	Description
data/no_website_emails_<town>_<service>_<date>.csv
Verified contact list for that market segment
data/sent_log.csv
Rolling record of all recipients already emailed
data/replies.csv
Archived reply summaries (sender, subject, snippet, date)
logs/
Process and cron output logs
🛡 Best Practices
✨ Use App Passwords & enable Gmail IMAP
📦 Rotate API keys every 90 days (Serper / Hunter)
🗂 Archive old logs monthly to keep lightweight
🚫 To pause outreach, comment out the second cronjob

bash

# pause cold emails
# 30 7 * * * cd ~/Scripts/Daily_Leads/src ... send_cold_emails.py
🧾 Version History 📅
Date	Update
2026‑02‑22
Added subject rotation, random send delays, Gmail reply processing, automatic cleanup, and reply notification emails.
❤️ Built by Alex Cahn / ZBA Digital — streamlining local lead generation through automation.

