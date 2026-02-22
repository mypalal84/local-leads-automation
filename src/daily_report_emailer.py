#!/usr/bin/env python3
"""
daily_report_emailer.py
----------------------------------------------------
1️⃣ Scans /data/ for today's CSV files
2️⃣ Zips them into one archive
3️⃣ Emails the zip to you
4️⃣ Moves yesterday's files → /archive/
----------------------------------------------------
"""

import os
import glob
import smtplib
import zipfile
import shutil
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()

EMAIL_FROM = os.getenv("DAILY_LEAD_EMAIL_SENDER")
EMAIL_PASS = os.getenv("DAILY_LEAD_EMAIL_PASS")
EMAIL_TO   = os.getenv("DAILY_LEAD_EMAIL_TO")

def make_zip(today_str, files, target_dir):
    """Compress today's CSVs into one ZIP file."""
    zip_path = os.path.join(target_dir, f"daily_leads_{today_str}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in files:
            zipf.write(path, os.path.basename(path))
    print(f"[📦] Created ZIP archive: {zip_path}")
    return zip_path

def send_email(zip_path):
    """Send the ZIP file as a single attachment via Gmail."""
    msg = MIMEMultipart()
    today = datetime.now().strftime("%A, %B %d, %Y")
    msg["From"], msg["To"], msg["Subject"] = (
        EMAIL_FROM,
        EMAIL_TO,
        f"ZBA Digital Daily Lead Reports – {today}",
    )

    body = (
        f"Hi,\n\nAttached is the consolidated ZIP file containing all lead "
        f"reports generated on {today}.\n\nAll older CSVs have been archived automatically.\n\n"
        "Best,\nZBA Automation Bot 🤖"
    )
    msg.attach(MIMEText(body, "plain"))

    with open(zip_path, "rb") as f:
        part = MIMEBase("application", "zip")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(zip_path)}"')
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f"[📧] Sent ZIP report to {EMAIL_TO}")

def archive_old_files(data_dir):
    """Move any files not from today into /archive/."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.path.join(data_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    files = glob.glob(os.path.join(data_dir, "*.csv"))
    moved = []

    for f in files:
        if today_str not in f:  # not today's file → archive
            dest = os.path.join(archive_dir, os.path.basename(f))
            shutil.move(f, dest)
            moved.append(os.path.basename(f))

    if moved:
        print(f"[🗃] Archived {len(moved)} older files → /archive/")
    else:
        print("[INFO] No files to archive today.")

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Step 1: collect today's CSVs
    matched = glob.glob(os.path.join(DATA_DIR, f"*{today_str}*.csv"))

    # Step 2: zip and email if there are results
    if not matched:
        print("[INFO] No CSV files found for today — skipping email.")
    else:
        zip_path = make_zip(today_str, matched, DATA_DIR)
        send_email(zip_path)

    # Step 3: move old CSVs to archive
    archive_old_files(DATA_DIR)

# --------------------------------------------------
#  Step 4:  Auto‑prune files older than 90 days
# --------------------------------------------------

def prune_archive(archive_dir, days=90):
    """Delete archived files older than N days."""
    cutoff = time.time() - (days * 86400)
    deleted = []
    for fname in os.listdir(archive_dir):
        path = os.path.join(archive_dir, fname)
        if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
            os.remove(path)
            deleted.append(fname)
    if deleted:
        print(f"[🧹] Pruned {len(deleted)} files older than {days} days → deleted.")
    else:
        print(f"[INFO] No old files to prune (older than {days} days).")

# Run prune after archiving completes
archive_dir = os.path.join(DATA_DIR, "archive")
if os.path.isdir(archive_dir):
    prune_archive(archive_dir)