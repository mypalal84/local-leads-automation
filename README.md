# Local Leads Automation

Automated lead generation for local service businesses with no website (or weak web presence), plus optional outreach email support.

**Last updated:** February 21, 2026

## Overview

This project helps identify local businesses and generate daily lead files for outbound outreach.

Core workflow:

1. Search for local businesses by town and service category.
2. Enrich contact data (email/domain) through API lookups.
3. Apply fallback email pattern guesses when enrichment is missing.
4. Export dated CSV outputs.
5. Optionally send summary/outreach emails.

## Features

- Automated lead discovery from configured towns/services.
- Contact enrichment with API-backed lookups.
- Fallback email pattern generation.
- Daily CSV export files.
- Optional scheduled execution via `launchd` (macOS) or cron.

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`
- API keys for your configured providers
- Optional Gmail App Password for SMTP sending

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Quick Start

1. Clone and enter the repo:

```bash
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
```

2. Create your environment file:

```bash
cp .env.example .env
```

3. Update `.env` with your keys and email credentials.

4. Run the lead generator:

```bash
python3 src/lead_generator_email.py
```

Or run via helper script:

```bash
bash scripts/run_leads.sh
```

## Environment Variables

The code currently reads these variables:

```env
GOOGLE_API_KEY=...
HUNTER_KEY=...
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
```

> Note: Keep `.env` private. Never commit real credentials.

## Project Structure

```text
Daily_Leads/
├── cleanup_daily_leads.sh
├── requirements.txt
├── data/
│   ├── lead_history.csv
│   └── towns_1000.csv
├── logs/
│   └── email_sent_YYYY-MM-DD.csv
├── scripts/
│   ├── examples.plist
│   ├── run_leads.sh
│   └── setup_env.sh
├── src/
│   ├── lead_generator_email.py
│   └── send_outreach_emails.py
└── templates/
            ├── intake_form.html
            └── outreach_email.txt
```

## Running on a Schedule

### macOS (`launchd`)

```bash
cp scripts/examples.plist ~/Library/LaunchAgents/com.dailyleads.generator.plist
launchctl load ~/Library/LaunchAgents/com.dailyleads.generator.plist
launchctl list | grep dailyleads
```

### Cron (alternative)

```bash
0 8 * * * cd ~/Scripts/Daily_Leads/src && /usr/bin/python3 lead_generator_email.py >> ~/Scripts/Daily_Leads/logs/cron_leads.log 2>&1
30 8 * * * cd ~/Scripts/Daily_Leads/src && /usr/bin/python3 send_outreach_emails.py >> ~/Scripts/Daily_Leads/logs/cron_outreach.log 2>&1
```

## Output

- Lead exports are written as dated CSV files in `src/`.
- Historical tracking is kept in `data/lead_history.csv`.
- Logs are written under `logs/`.

## Security Notes

- Do not commit `.env` or credential files.
- Use Gmail App Passwords instead of your primary login password.
- Rotate API keys if you suspect leakage.

## License

MIT — see `LICENSE`.