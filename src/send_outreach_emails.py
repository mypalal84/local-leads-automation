import os
import pandas as pd
import smtplib
import time, random
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv
from jinja2 import Template

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
# --- Remove duplicate emails (avoid duplicate sends) ---
df = df.drop_duplicates(subset=["Email"])

import glob

# --- Exclude previously contacted emails (already sent in logs) ---
sent_emails = set()

# Find all sent logs
log_files = glob.glob(os.path.join(os.path.dirname(__file__), "../logs/email_sent_*.csv"))
for log in log_files:
    try:
        old = pd.read_csv(log)
        if "Email" in old.columns:
            sent_emails.update(old["Email"].dropna().unique().tolist())
    except Exception as e:
        print(f"⚠️ Could not read log {log}: {e}")

# Remove any rows whose 'Email' was already emailed in a prior run
df = df[~df["Email"].isin(sent_emails)]

print(f"✅ {len(df)} leads remaining after removing previously contacted emails.\n")

# --- Load template ---
template_path = os.path.join(os.path.dirname(__file__), "../templates/outreach_email.txt")
with open(template_path) as f:
    template = Template(f.read())

# --- SMTP Setup ---
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
sent_log = []
for _, row in df.iterrows():
    time.sleep(random.uniform(8, 15))  # waits 8–15 seconds per send
    body = template.render(business=row["Business"], service=row["Service"], town=row["Town"])
    subject = f"Professional website for {row['Business']}"
    try:
        send_email(row["Email"], subject, body)
        print(f"📨 Sent to {row['Email']}")
        sent_log.append(row)
    except Exception as e:
        print(f"⚠️ Failed to send to {row['Email']}: {e}")

# --- Save log ---
if sent_log:
    sent_df = pd.DataFrame(sent_log)
    log_dir = os.path.join(os.path.dirname(__file__), "../logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"email_sent_{datetime.now().strftime('%Y-%m-%d')}.csv")
    sent_df.to_csv(log_path, index=False)
    print(f"\n✅ Log saved to {log_path}")
else:
    print("No emails sent.")