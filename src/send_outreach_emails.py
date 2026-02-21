#!/usr/bin/env python3
import os
import pandas as pd
import smtplib
import time, random, glob
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv
from jinja2 import Template

# ==============================================================
#   ZBA Digital – Daily Outreach Script (with Summary + Bounces)
# ==============================================================

# Load credentials
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# --- Locate latest CSV ---
SRC_DIR = os.path.join(os.path.dirname(__file__), "")
csv_files = [f for f in os.listdir(SRC_DIR) if f.startswith("daily_enriched_leads_")]
if not csv_files:
    print("No lead files found.")
    exit()

latest_csv = max(csv_files)
print(f"📄 Using lead file: {latest_csv}")
df = pd.read_csv(os.path.join(SRC_DIR, latest_csv))

# --- Filter ---
df = df[df["Source"] == "Hunter.io"]
df = df[df["Email"].notna() & ~df["Email"].str.contains("gmail|yahoo|outlook|hotmail", case=False)]
df = df.drop_duplicates(subset=["Email"])  # remove duplicate emails

# --- Exclude previously contacted emails (already sent in logs) ---
sent_emails = set()
log_files = glob.glob(os.path.join(os.path.dirname(__file__), "../logs/email_sent_*.csv"))
for log in log_files:
    try:
        old = pd.read_csv(log)
        old.columns = [c.strip().lower() for c in old.columns]
        if "email" in old.columns:
            sent_emails.update(old["email"].dropna().str.strip().unique().tolist())
    except Exception as e:
        print(f"⚠️ Could not read log {log}: {e}")

print(f"Found {len(sent_emails)} previously contacted emails")

# --- Exclude known bounces ---
bounce_file = os.path.join(os.path.dirname(__file__), "../logs/bounced_emails.csv")
bounced_emails = set()
if os.path.exists(bounce_file):
    try:
        bounces = pd.read_csv(bounce_file)
        bounces.columns = [c.strip().lower() for c in bounces.columns]
        if "email" in bounces.columns:
            bounced_emails.update(bounces["email"].dropna().str.strip().unique().tolist())
        print(f"Found {len(bounced_emails)} bounced / invalid emails")
    except Exception as e:
        print(f"⚠️ Could not read {bounce_file}: {e}")

# --- Combine exclusion lists ---
df["Email"] = df["Email"].str.strip()
df = df[~df["Email"].isin(sent_emails | bounced_emails)]

print(f"✅ {len(df)} leads remaining after removing contacted + bounced emails.\n")

# --- Load template ---
template_path = os.path.join(os.path.dirname(__file__), "../templates/outreach_email.txt")
with open(template_path) as f:
    template = Template(f.read())

# --- SMTP send helper ---
def send_email(recipient, subject, body):
    FROM_NAME = "Alex – ZBA Digital"
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{EMAIL_USER}>"
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

# --- Send loop ---
sent_log, bounce_log = [], []
for _, row in df.iterrows():
    time.sleep(random.uniform(8, 15))  # waits 8–15 seconds per send
    body = template.render(business=row["Business"], service=row["Service"], town=row["Town"])
    subject = f"Professional website for {row['Business']}"
    try:
        send_email(row["Email"], subject, body)
        print(f"📨 Sent to {row['Email']}")
        sent_log.append(row)
    except smtplib.SMTPRecipientsRefused:
        print(f"❌ Bounce: {row['Email']} not found")
        bounce_log.append({"Email": row["Email"], "Business": row["Business"]})
    except Exception as e:
        print(f"⚠️ Failed to send to {row['Email']}: {e}")

# --- Save logs ---
log_dir = os.path.join(os.path.dirname(__file__), "../logs")
os.makedirs(log_dir, exist_ok=True)

# Sent log
if sent_log:
    sent_df = pd.DataFrame(sent_log)
    path_sent = os.path.join(log_dir, f"email_sent_{datetime.now().strftime('%Y-%m-%d')}.csv")
    sent_df.to_csv(path_sent, index=False)
    print(f"\n✅ Log saved to {path_sent}")

# Bounce log
if bounce_log:
    b_df = pd.DataFrame(bounce_log)
    if os.path.exists(bounce_file):
        existing = pd.read_csv(bounce_file)
        b_df = pd.concat([existing, b_df], ignore_index=True).drop_duplicates(subset=["Email"])
    b_df.to_csv(bounce_file, index=False)
    print(f"⚠️ {len(bounce_log)} bounced emails added to {bounce_file}")

# -----------------------------------------------------------
#   Email summary report to yourself
# -----------------------------------------------------------
summary_subject = "ZBA Digital Daily Outreach Summary"
sent_count = len(sent_log)
bounce_count = len(bounce_log)
skipped_count = len(sent_emails) + len(bounced_emails)

summary_body = (
    f"✅ Daily outreach completed.\n\n"
    f"• Sent: {sent_count}\n"
    f"• Bounced: {bounce_count}\n"
    f"• Skipped (already contacted or bounced): {skipped_count}\n\n"
    f"📄 Leads file: {latest_csv}\n"
    f"🕒 Timestamp: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n\n"
    f"— ZBA Digital Automation"
)

msg = MIMEText(summary_body, "plain")
msg["Subject"] = summary_subject
msg["From"] = f"ZBA Digital Automation <{EMAIL_USER}>"
msg["To"] = EMAIL_USER

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)
    print(f"\n📨 Summary email sent to {EMAIL_USER}")
except Exception as e:
    print(f"⚠️ Failed to send summary email: {e}")