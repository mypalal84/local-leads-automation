# 🌐 Local Leads Automation

> Automated lead generation for local service businesses with no or outdated websites.  
> Built with **Python** using **Google Places**, **Serper**, **SerpAPI**, and **Hunter.io** APIs.  
> **Last Updated:** February 22 2026

---

## 🚀 Overview

**Local Leads Automation** identifies owner‑operated small businesses that lack a functional website — the ideal audience for **ZBA Digital’s 7‑Day Website Service**.

The system automatically:

1. 🔍 Scrapes business listings from **Google Places API**  
2. 🚫 Detects listings with no working website  
3. ✉️ Enriches contact info via **Serper → SerpAPI → Hunter.io**  
4. 🧩 Falls back to intelligent email pattern guesses (`info@`, `contact@`, etc.)  
5. 📦 Exports results to CSV and emails a daily summary  
6. 🔁 Can run completely automated on a schedule  

It powers the **ZBA Digital** productized service: fixed scope • fixed price • fixed delivery.

---

## ⚡ Quick Start

Clone the repository and install requirements:
bash
git clone https://github.com/&lt;YOUR_USERNAME&gt;/&lt;YOUR_REPO&gt;.git
cd &lt;YOUR_REPO&gt;
python3 -m pip install -r requirements.txt
Then set up your environment variables:

bash

cp .env.example .env && nano .env
Finally, run your first pass:

bash

python3 src/lead_generator_no_website_enriched.py
📦 Repository Structure
text

~/Scripts/Daily_Leads/
│
├── src/
│   └── lead_generator_no_website_enriched.py
│
├── data/
│   ├── towns_1000.csv          # Town + state + population
│   └── README.md
│
├── scripts/
│   ├── run_leads.sh            # Manual trigger
│   ├── setup_env.sh
│   └── examples.plist          # macOS launchd template
│
├── logs/
│   ├── daily_run.log           # Successful runs
│   ├── daily_run_error.log     # Errors, API issues
│   └── README.md
│
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
🧰 Requirements
Python ≥ 3.10
Dependencies
bash

pip install -r requirements.txt
Key Packages

requests – API calls
pandas – CSV handling + data prep
python-dotenv – secure API key loading
🔑 Required API Keys
Service	Purpose
Google Places API
Discover local businesses
Serper API
Enrich missing web data
SerpAPI
Validate and scrape site presence
Hunter.io
Find emails and domains
Optional (Email Reports):
Use a Gmail account with an App Password to send daily summaries.

⚙️ Setup Instructions
1. Clone the repository
bash

git clone https://github.com/&lt;YOUR_USERNAME&gt;/&lt;YOUR_REPO&gt;.git
cd &lt;YOUR_REPO&gt;
2. Install the requirements
bash

python3 -m pip install -r requirements.txt
3. Add environment variables
bash

cp .env.example .env && nano .env
4. Fill in your .env file
bash

SERPER_API_KEY=xxxxxx
SERPAPI_API_KEY=xxxxxx
HUNTER_API_KEY=xxxxxx
GOOGLE_PLACES_API_KEY=xxxxxx

DAILY_LEAD_EMAIL_SENDER=your_email@gmail.com
DAILY_LEAD_EMAIL_PASS=your_app_password
DAILY_LEAD_EMAIL_TO=your_email@gmail.com
▶️ Running the Script
Manual execution
bash

python3 src/lead_generator_no_website_enriched.py
Or use the helper script
bash

bash scripts/run_leads.sh
Each run automatically:
Generates a dated CSV in /data
Sends you an email summary (if configured)
Appends new entries to lead_history.csv
🕒 Automating Daily Runs
macOS – launchd
bash

cp scripts/examples.plist ~/Library/LaunchAgents/com.dailyleads.generator.plist
launchctl load ~/Library/LaunchAgents/com.dailyleads.generator.plist
launchctl list | grep dailyleads
💡 Schedule around 8 AM local time and ensure your Mac is awake.

Cron (Alternative)
bash

0 8 * * * cd ~/Scripts/Daily_Leads/src && /usr/bin/python3 lead_generator_email.py >> ~/Scripts/Daily_Leads/logs/cron_leads.log 2>&1
30 8 * * * cd ~/Scripts/Daily_Leads/src && /usr/bin/python3 send_outreach_emails.py >> ~/Scripts/Daily_Leads/logs/cron_outreach.log 2>&1
📊 Example Output
Business Name	Phone	Email (Enriched)	Provider Used	Town	Service	Rating	Google Maps Link
Joe’s Plumbing
(206) 555‑1212
info@joesplumbing.com
Serper
Seattle
Plumbing
 4.8 
 maps.google.com/... 
🌐 Pipeline Flow Diagram
text

         Google Places API
               │
               ▼
         Business List
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
 Serper.dev  SerpAPI   Hunter.io
   │           │           │
   └───────► Email Enrichment ◄──────┘
               │
        Pattern Guess Fallback
               │
               ▼
           CSV Export
               │
               ▼
        Daily Email Summary
🧩 Fallback Logic
If any primary API fails or reaches quota:

1. Try Serper → SerpAPI → Hunter.io
2. If still missing, build a patterned guess (info@domain, contact@domain)

✅ Ensures every found business has at least one email for outreach.

💾 Logs & Lead History
File	Purpose
daily_run.log
Timestamped execution summary
daily_run_error.log
Captures exceptions and API issues
All existing leads are tracked in lead_history.csv to avoid duplicates.

🔒 Security Notes
Keep .env private (never commit to GitHub).
.gitignore already excludes .env, logs/, and CSV exports.
Use App Passwords for Gmail authentication, not your main login.
📜 License
Released under the MIT License
Free for personal and commercial use with attribution.

🤝 Acknowledgments
Google Places API
Serper.dev
SerpAPI
Hunter.io
✨ How ZBA Digital Uses This Tool
The generated CSV feeds directly into ZBA Digital’s local outreach system, where each new lead triggers:

Personalized outreach email
Stripe checkout payment link
Intake form and asset collection
Site build start within 7 days
This allows ZBA Digital to attract, qualify, and onboard new clients automatically — no discovery calls, no uncontrolled scope.

Author: ZBA Digital – Productized Website Automation
License: MIT
Updated: February 22 2026