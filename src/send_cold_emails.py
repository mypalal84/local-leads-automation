#!/usr/bin/env python3
"""
send_cold_emails.py — Final Version
------------------------------------------------------
Dynamic cold-email sender with subject rotation,
delay randomization, and reply‑based cleanup.
------------------------------------------------------
"""

import os, smtplib, ssl, csv, time, random, imaplib, email, re
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv
from glob import glob
import pandas as pd

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
EMAIL_ADDR = os.getenv("DAILY_LEAD_EMAIL_SENDER")
EMAIL_PASS = os.getenv("DAILY_LEAD_EMAIL_PASS")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
IMAP_SERVER = "imap.gmail.com"

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
SENT_LOG = os.path.join(DATA_DIR, "sent_log.csv")
REPLIES_FILE = os.path.join(DATA_DIR, "replies.csv")
REPLY_NOTIFY_TO = os.getenv("REPLY_NOTIFY_TO", EMAIL_ADDR)

# --------------------------------------------------
# Message templates
# --------------------------------------------------
SUBJECTS = [
    "Quick question about {business}",
    "Website for {business}?",
    "Helping {business} get more calls online",
    "{business} + mobile site idea",
    "{business}: quick note",
]

BODY_TEMPLATE = """Hi {business},

I came across {business} while checking {service} providers in {town}.
I help local owners like you launch professional, mobile‑friendly websites that attract more calls — within 7 days.

Is this something you’d be open to exploring for {business}?

Best,
Alex
ZBA Digital
www.zbadigital.com
"""

# --------------------------------------------------
# Helper utilities
# --------------------------------------------------
def load_sent_log():
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG, newline="") as f:
        return set(row[0].strip().lower() for row in csv.reader(f))

def append_to_log(email):
    with open(SENT_LOG, "a", newline="") as f:
        csv.writer(f).writerow([email.lower()])

def remove_from_log(replied_emails):
    if not os.path.exists(SENT_LOG): return
    df = pd.read_csv(SENT_LOG, header=None, names=["email"])
    df = df[~df["email"].isin(replied_emails)]
    df.to_csv(SENT_LOG, header=False, index=False)

def find_latest_verified_file():
    files = sorted(glob(os.path.join(DATA_DIR, "no_website_emails_*_*.csv")), reverse=True)
    return files[0] if files else None

def parse_context_from_filename(fname):
    # Expected pattern: no_website_emails_<town>_<service>_<DATE>.csv
    m = re.search(r"no_website_emails_(.+)_(.+)_\d{4}-\d{2}-\d{2}", os.path.basename(fname))
    if m:
        town, service = m.groups()
        return town.replace("-", " ").title(), service.replace("-", " ")
    return "Your Town", "Your Service"

# --------------------------------------------------
# Core: send emails
# --------------------------------------------------
def send_cold_emails():
    sent = load_sent_log()
    csv_file = find_latest_verified_file()
    if not csv_file:
        print("[ERR] No verified leads file found.")
        return

    town, service = parse_context_from_filename(csv_file)
    context = ssl.create_default_context()

    print(f"[INFO] Sending from file: {os.path.basename(csv_file)} ({town}, {service})")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(EMAIL_ADDR, EMAIL_PASS)

        with open(csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email_field = row.get("emails","").split(",")[0].strip().lower()
                if not email_field or email_field in sent:
                    continue

                business = row.get("name","your company").strip()
                subject = random.choice(SUBJECTS).format(business=business)
                body = BODY_TEMPLATE.format(business=business, town=town, service=service)

                msg = MIMEText(body, "plain", "utf-8")
                msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_ADDR, email_field

                try:
                    server.sendmail(EMAIL_ADDR, [email_field], msg.as_string())
                    append_to_log(email_field)
                    print(f"[SENT] {business} → {email_field} | {subject}")
                    time.sleep(random.uniform(1,5))
                except Exception as e:
                    print(f"[ERR] {email_field}: {e}")

    print("[INFO] Outbound cold-email batch finished.\n")
    replied = fetch_replies()  # cleanup
    if replied:
        remove_from_log(replied)
        print(f"[CLEANUP] Removed {len(replied)} replied emails from future sends.\n")

# --------------------------------------------------
# Reply tracking (IMAP)
# --------------------------------------------------
def decode_fragment(x):
    if not x: return ""
    if isinstance(x, bytes): return x.decode(errors="ignore")
    return x

def fetch_replies():
    """Look back 7 days for replies."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDR, EMAIL_PASS)
        mail.select("inbox")

        since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'(SINCE "{since}")')
        if status != "OK" or not data[0]:
            mail.logout()
            return []

        ids = data[0].split()
        print(f"[INFO] Checking {len(ids)} recent messages for replies...")
        replied_addresses = set()

        with open(REPLIES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for i in ids:
                typ, msg_data = mail.fetch(i, "(RFC822)")
                if typ != "OK": continue
                msg = email.message_from_bytes(msg_data[0][1])

                frm = msg.get("From", "")
                subject, enc = decode_header(msg.get("Subject",""))[0]
                subject = decode_fragment(subject)

                if any(tok in subject.lower() for tok in ["question", "website", "mobile site", "call"]):
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = decode_fragment(part.get_payload(decode=True)[:150]).replace("\n"," ")
                                break
                    else:
                        body = decode_fragment(msg.get_payload(decode=True))[:150].replace("\n"," ")
                    date = msg.get("Date","")
                    writer.writerow([frm, subject, body, date])
                    m2 = re.search(r"<([^>]+)>", frm)
                    if m2:
                        replied_addresses.add(m2.group(1).lower())
                        print(f"[REPLY] {m2.group(1)} | {subject}")

        mail.logout()
        if replied_addresses:
            send_reply_notifications(replied_addresses)
        return replied_addresses
    except Exception as e:
        print("[ERR] Reply check failed:", e)
        return set()
# --------------------------------------------------
# NEW: Send notification email with summary
# --------------------------------------------------
def send_reply_notifications(replied_addresses):
    """Send a summary email listing new replies."""
    if not replied_addresses:
        return
    try:
        # read the latest 5 entries from replies.csv
        latest_rows = []
        if os.path.exists(REPLIES_FILE):
            with open(REPLIES_FILE, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
                latest_rows = rows[-5:] if len(rows) > 5 else rows

        summary_lines = []
        for r in latest_rows:
            if len(r) >= 4:
                summary_lines.append(f"- {r[0]} | {r[1]} | {r[2][:80]}...")

        body = (
            "New replies detected:\n\n" + "\n".join(summary_lines) +
            f"\n\nTotal replied addresses: {len(replied_addresses)}"
        )

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[Pipeline] {len(replied_addresses)} new replies"
        msg["From"] = EMAIL_ADDR
        msg["To"] = REPLY_NOTIFY_TO

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as s:
            s.login(EMAIL_ADDR, EMAIL_PASS)
            s.sendmail(EMAIL_ADDR, [REPLY_NOTIFY_TO], msg.as_string())

        print(f"[NOTIFY] Sent reply summary to {REPLY_NOTIFY_TO}")
    except Exception as e:
        print("[ERR] Reply notification failed:", e)

# --------------------------------------------------
if __name__ == "__main__":
    send_cold_emails()