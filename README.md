🌐 Local Leads Automation
Automated lead generation for local service businesses with no or outdated websites.
Built with Python using Google Places, Serper, SerpAPI, and Hunter.io APIs.

PythonBuildLicense

🚀 Overview
Local Leads Automation helps owner‑operated businesses get noticed online by identifying service providers who still lack a functional website. The system:

Scrapes small business listings from Google Places.
Detects entries without a working website.
Tries to locate contact emails via Serper → SerpAPI → Hunter.io.
Falls back to intelligent “pattern” guesses (info@, contact@).
Exports results to CSV and optionally emails a daily snapshot.
Designed for ZBA Digital’s productized website service workflow (fixed scope, fixed price, fixed delivery).

📁 Repository Structure
text

~/Scripts/Daily_Leads/
├── src/
│   └── lead_generator_no_website_enriched.py
├── data/
│   ├── towns_1000.csv
│   └── README.md
├── scripts/
│   ├── run_leads.sh
│   ├── setup_env.sh
│   └── examples.plist
├── logs/
│   ├── daily_run.log
│   ├── daily_run_error.log
│   └── README.md
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
🧰 Requirements
Python 3.10+

Packages:

code

requests
pandas
python-dotenv
API keys (required):

Google Places API
Serper API
SerpAPI
Hunter.io
Email (optional):

Gmail account with an App Password for sending reports
⚙️ Setup
Clone your repository and install dependencies:

bash

git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
python3 -m pip install -r requirements.txt
Create a .env file (based on .env.example) in the project root:

bash

cp .env.example .env
Then fill in your API keys and Gmail credentials:

bash

nano .env
Example .env:

code

SERPER_API_KEY=xxxxxx
SERPAPI_API_KEY=xxxxxx
HUNTER_API_KEY=xxxxxx
GOOGLE_PLACES_API_KEY=xxxxxx

DAILY_LEAD_EMAIL_SENDER=your_email@gmail.com
DAILY_LEAD_EMAIL_PASS=your_app_password
DAILY_LEAD_EMAIL_TO=your_email@gmail.com
▶️ Running Manually
bash

python3 src/lead_generator_no_website_enriched.py
or, using the convenience script:

bash

bash scripts/run_leads.sh
Each run:

Creates a dated CSV file in data/
Emails you a summary (if configured)
Appends new records to lead_history.csv
🕒 Scheduling (macOS + launchd example)
You can automate daily runs using launchd:

Copy scripts/examples.plist to:
bash

~/Library/LaunchAgents/com.dailyleads.generator.plist
Load it:
bash

launchctl load ~/Library/LaunchAgents/com.dailyleads.generator.plist
Confirm it’s active:
bash

launchctl list | grep dailyleads
TIP: Schedule for 8 AM local time, ensure your Mac is awake before that.

📊 Output Example
Business Name	Phone	Email (Enriched)	Provider Used	Town	Service	Rating	Google Maps Link
Joe’s Plumbing
(206) 555‑1212
info@joesplumbing.com
Serper
Seattle
Plumbing
4.8
google.com/maps/...
🧩 Fallback Logic
If higher‑tier APIs fail or run out of credits: 1. Serper → SerpAPI → Hunter.io
2. If still missing, pattern guess (info@, contact@, etc.).
This ensures every entry has at least one email candidate for outreach.

💾 Logs & History
All logs are stored in the logs/ directory: - daily_run.log  → timestamped runs
- daily_run_error.log  → exceptions or API errors

Existing leads are tracked in lead_history.csv to eliminate duplicates.

🔒 Security Notes
Keep your .env file private.
Never commit API keys to GitHub.
.gitignore already excludes .env, logs & runtime CSVs.
📄 License
Released under the MIT License.

🤝 Acknowledgments
Google Places API
Serper.dev
SerpAPI
Hunter.io