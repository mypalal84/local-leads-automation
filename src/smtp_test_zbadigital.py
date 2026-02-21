#!/usr/bin/env python3
# =============================================
#  Gmail / Workspace SMTP test for ZBA Digital
#  Confirms connection and sends one message
# =============================================

import os, smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# --- Load credentials from .env ---
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# --- Edit recipient if you want to test sending to another inbox ---
TO_ADDRESS = EMAIL_USER   # Send to yourself by default
SUBJECT = "✅ Test message from ZBA Digital Python Mailer"
BODY = (
    "Hello Alex,\n\n"
    "This is a test email sent automatically by your Python script "
    "using the new Google Workspace account (alex@zbadigital.com).\n\n"
    "If you receive this message, your SMTP settings are working correctly!\n\n"
    "— ZBA Digital Automation Test"
)

# --- Assemble email ---
msg = MIMEText(BODY, "plain")
msg["Subject"] = SUBJECT
msg["From"] = f"Alex – ZBA Digital <{EMAIL_USER}>"
msg["To"] = TO_ADDRESS

# --- Connect and send via Gmail / Workspace SMTP ---
try:
    print(f"Connecting as {EMAIL_USER} ...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print(f"✅  Test email successfully sent to {TO_ADDRESS}")
except Exception as e:
    print("❌  Failed to send test email:", e)