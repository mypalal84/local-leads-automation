#!/usr/bin/env python3
"""
daily_summary_report.py
------------------------------------------------------
Simple cron‑friendly summary emailer.
It scans today's no_website_emails_*.csv files,
counts totals, and sends a one‑paragraph summary
email (no attachments).
------------------------------------------------------
"""

import os, glob, smtplib, time, pandas as pd
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import datetime

# --------------------------------------------------
# Setup
# --------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
EMAIL_FROM = os.getenv("DAILY_LEAD_EMAIL_SENDER")
EMAIL_PASS = os.getenv("DAILY_LEAD_EMAIL_PASS")
EMAIL_TO   = os.getenv("DAILY_LEAD_EMAIL_TO")

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data", "current")
TODAY     = datetime.now().strftime("%Y-%m-%d")

# --------------------------------------------------
# Compose message
# --------------------------------------------------
def build_summary():
    files = sorted(glob.glob(os.path.join(DATA_DIR, f"no_website_emails_*_{TODAY}.csv")))
    if not files:
        return f"No 'no_website_emails' files found for {TODAY}."

    total_files, total_rows, total_emails = 0, 0, 0
    lines = []
    for path in files:
        try:
            df = pd.read_csv(path)
            num_leads = len(df)
            num_with_email = df['emails'].notnull().sum()
            total_rows += num_leads
            total_emails += num_with_email
            total_files += 1
            city_service = os.path.basename(path).replace(f"_no_website_emails_","").replace(f"_{TODAY}.csv","")
            lines.append(f"• {city_service}: {num_with_email}/{num_leads} leads with emails")
        except Exception as e:
            lines.append(f"⚠️ Error reading {os.path.basename(path)}: {e}")

    header = f"""
ZBA Digital — Daily Lead Summary ({TODAY})
--------------------------------------------------
Files processed : {total_files}
Total leads     : {total_rows}
Emails found    : {total_emails}
--------------------------------------------------
"""
    return header + "\n".join(lines)

# --------------------------------------------------
# Send summary email
# --------------------------------------------------
def send_summary_email(body):
    msg = MIMEText(body, "plain")
    msg["Subject"] = f"ZBA Digital Daily Lead Summary — {TODAY}"
    msg["From"], msg["To"] = EMAIL_FROM, EMAIL_TO

    last_exc = None
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_FROM, EMAIL_PASS)
                server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            print(f"[ERROR] SMTP summary send failed attempt {attempt + 1}/3: {exc}")
            if attempt < 2:
                time.sleep(3 ** attempt)

    if last_exc is not None:
        raise last_exc

    print("[✅] Sent summary email to", EMAIL_TO)

# --------------------------------------------------
if __name__ == "__main__":
    summary = build_summary()
    print(summary)
    send_summary_email(summary)