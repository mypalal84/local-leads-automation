# Local Leads Automation

Automated lead generation for local service businesses with no website.  
Uses **Google Places**, **Serper**, **SerpAPI**, and **Hunter.io** APIs to collect, enrich, and email new leads daily.

## 🚀 Features
- Finds small owner-operated service businesses lacking a website
- Enriches contacts via Serper → SerpAPI → Hunter fallback
- Outputs a CSV report and optionally emails it daily
- One‑step scheduling via `launchd` or cron

## 📋 Requirements
- Python 3.10+
- API keys for:
  - Google Places
  - Serper
  - SerpAPI
  - Hunter.io
- Gmail account + App Password (for emailing CSVs)

## 🧰 Installation
```bash
git clone https://github.com/&lt;your‑username&gt;/local-leads-automation.git
cd local-leads-automation
pip install -r requirements.txt