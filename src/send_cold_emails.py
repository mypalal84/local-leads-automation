#!/usr/bin/env python3
"""
send_cold_emails.py — Final Version
------------------------------------------------------
Dynamic cold-email sender with subject rotation,
delay randomization, and reply‑based cleanup.
------------------------------------------------------
"""

import os, smtplib, ssl, csv, time, random, imaplib, email, re, sys
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv
from glob import glob
from urllib.parse import urlparse
import pandas as pd
import dns.resolver

try:
    import certifi
except Exception:
    certifi = None

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
SUPPRESSIONS_FILE = os.path.join(DATA_DIR, "suppressions.csv")
PROCESSED_REPLY_IDS_FILE = os.path.join(DATA_DIR, "processed_reply_message_ids.csv")
REPLY_NOTIFY_TO = os.getenv("REPLY_NOTIFY_TO", EMAIL_ADDR)
DAILY_EMAIL_TARGET = int(os.getenv("DAILY_EMAIL_TARGET", "50"))
LEAD_SCORE_THRESHOLD = int(os.getenv("LEAD_SCORE_THRESHOLD", "2"))
PRE_SEND_VALIDATE_EMAILS = os.getenv("PRE_SEND_VALIDATE_EMAILS", "true").strip().lower() in {"1", "true", "yes", "on"}
MAX_EMAILS_PER_DOMAIN = int(os.getenv("MAX_EMAILS_PER_DOMAIN", "2"))
BLOCK_GENERIC_INBOXES = os.getenv("BLOCK_GENERIC_INBOXES", "true").strip().lower() in {"1", "true", "yes", "on"}
UNSUBSCRIBE_FOOTER = os.getenv(
    "UNSUBSCRIBE_FOOTER",
    "If you'd prefer not to hear from me again, reply STOP and I will remove you immediately.",
)
DAILY_SENT_LOG = os.path.join(DATA_DIR, f"daily_sent_{datetime.now().strftime('%Y-%m-%d')}.csv")
NEGATIVE_REPLY_KEYWORDS = [
    "unsubscribe", "stop", "remove", "do not contact", "don't contact",
    "not interested", "no thanks", "no thank you", "wrong email", "spam"
]
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"
}
NON_BUSINESS_RECIPIENT_DOMAINS = {
    "indeed.com", "linkedin.com", "wikipedia.org", "va.gov", "usa.gov",
    "yelp.com", "bbb.org", "homeadvisor.com", "angi.com", "thumbtack.com",
    "zoominfo.com", "manta.com", "mapquest.com", "yellowpages.com",
    "consumeraffairs.com",
}
NON_BUSINESS_SOURCE_DOMAINS = {
    "yelp.com", "bbb.org", "homeadvisor.com", "angi.com", "thumbtack.com",
    "zoominfo.com", "manta.com", "wikipedia.org", "wikimedia.org", "fandom.com",
    "indeed.com", "linkedin.com", "yellowpages.com", "mapquest.com", "zocdoc.com",
    "consumeraffairs.com",
}
NON_BUSINESS_TEXT_HINTS = [
    "[pdf]", "pdf", "jobs", "job", "employment", "salary", "career", "careers",
    "university", "department of", "federal", "government", "wikipedia",
    "directory", "reviews", "top 10", "wiki", "| page",
]
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GENERIC_LOCAL_PARTS = {
    "info", "admin", "support", "sales", "contact", "office", "hello", "team", "service", "customerservice"
}
AUTO_REPLY_SUBJECT_TOKENS = [
    "automatic reply", "auto reply", "out of office", "ooo", "away from the office", "vacation"
]
DSN_SUBJECT_TOKENS = [
    "delivery incomplete", "delivery status notification", "undeliverable", "failure notice",
    "mail delivery subsystem", "delivery failure", "message blocked", "message not delivered"
]
HARD_BOUNCE_HINT_TOKENS = [
    "recipient server did not accept", "failed_precondition", "connect error", "connection refused",
    "user unknown", "no such user", "mailbox unavailable", "address not found", "invalid recipient"
]
SOFT_BOUNCE_HINT_TOKENS = [
    "temporarily", "try again later", "deferred", "greylist", "rate limit"
]
MX_CACHE = {}

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

def append_to_daily_log(email):
    with open(DAILY_SENT_LOG, "a", newline="") as f:
        csv.writer(f).writerow([email.lower()])

def load_suppression_list():
    if not os.path.exists(SUPPRESSIONS_FILE):
        return set()
    with open(SUPPRESSIONS_FILE, newline="", encoding="utf-8") as f:
        rows = csv.reader(f)
        return set(row[0].strip().lower() for row in rows if row and row[0].strip())

def append_to_suppressions(email_addr, reason="manual"):
    email_addr = (email_addr or "").strip().lower()
    if not email_addr:
        return
    existing = load_suppression_list()
    if email_addr in existing:
        return
    with open(SUPPRESSIONS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([email_addr, reason, datetime.now().isoformat(timespec="seconds")])

def extract_email_address(from_field):
    m = re.search(r"<([^>]+)>", from_field or "")
    if m:
        return m.group(1).strip().lower()
    m2 = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", from_field or "")
    return m2.group(0).strip().lower() if m2 else ""

def load_daily_sent_count():
    if not os.path.exists(DAILY_SENT_LOG):
        return 0
    try:
        with open(DAILY_SENT_LOG, newline="") as f:
            return sum(1 for _ in csv.reader(f))
    except Exception:
        return 0


def load_daily_domain_counts():
    counts = {}
    if not os.path.exists(DAILY_SENT_LOG):
        return counts
    try:
        with open(DAILY_SENT_LOG, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                email_addr = (row[0] or "").strip().lower()
                if "@" not in email_addr:
                    continue
                domain = email_addr.split("@")[-1]
                counts[domain] = counts.get(domain, 0) + 1
    except Exception:
        return counts
    return counts


def is_generic_inbox(email_addr):
    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return False
    local_part = email_addr.split("@")[0]
    return local_part in GENERIC_LOCAL_PARTS


def extract_contact_name(email_addr):
    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return "there"
    local_part = email_addr.split("@")[0]
    token = re.split(r"[._+\-]", local_part)[0].strip()
    if not token or token in GENERIC_LOCAL_PARTS:
        return "there"
    if not token.isalpha() or len(token) < 2:
        return "there"
    return token.capitalize()

def remove_from_log(replied_emails):
    if not os.path.exists(SENT_LOG): return
    df = pd.read_csv(SENT_LOG, header=None, names=["email"])
    df = df[~df["email"].isin(replied_emails)]
    df.to_csv(SENT_LOG, header=False, index=False)


def load_processed_message_ids():
    if not os.path.exists(PROCESSED_REPLY_IDS_FILE):
        return set()
    with open(PROCESSED_REPLY_IDS_FILE, newline="", encoding="utf-8") as f:
        rows = csv.reader(f)
        return set(row[0].strip() for row in rows if row and row[0].strip())


def append_processed_message_id(message_id):
    message_id = (message_id or "").strip()
    if not message_id:
        return
    with open(PROCESSED_REPLY_IDS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([message_id])


def is_auto_reply(msg, subject):
    subject_lower = (subject or "").lower()
    if any(token in subject_lower for token in AUTO_REPLY_SUBJECT_TOKENS):
        return True

    auto_submitted = (msg.get("Auto-Submitted", "") or "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return True

    if msg.get("X-Autoreply") or msg.get("X-Autorespond"):
        return True

    precedence = (msg.get("Precedence", "") or "").strip().lower()
    if precedence in {"bulk", "list", "junk", "auto_reply"}:
        return True

    return False


def is_valid_email_syntax(email_addr):
    return bool(EMAIL_REGEX.match((email_addr or "").strip()))


def has_mx_record(domain):
    domain = (domain or "").strip().lower()
    if not domain:
        return False
    if domain in MX_CACHE:
        return MX_CACHE[domain]
    try:
        answers = dns.resolver.resolve(domain, "MX")
        MX_CACHE[domain] = len(list(answers)) > 0
    except Exception:
        MX_CACHE[domain] = False
    return MX_CACHE[domain]


def should_send_to_email(email_addr):
    email_addr = (email_addr or "").strip().lower()
    if not is_valid_email_syntax(email_addr):
        return False, "invalid_syntax"
    domain = email_addr.split("@")[-1]
    if not has_mx_record(domain):
        return False, "no_mx"
    return True, "ok"


def is_delivery_status_notification(msg, subject):
    subject_lower = (subject or "").lower()
    if any(token in subject_lower for token in DSN_SUBJECT_TOKENS):
        return True

    from_lower = (msg.get("From", "") or "").lower()
    if "mailer-daemon" in from_lower or "mail delivery subsystem" in from_lower:
        return True

    content_type = (msg.get_content_type() or "").lower()
    if content_type == "multipart/report":
        return True

    return False


def classify_bounce_type(subject, body_text):
    text = f"{subject or ''} {body_text or ''}".lower()
    if re.search(r"\b5\d\d\b|\b5\.\d\.\d\b", text):
        return "hard"
    if re.search(r"\b4\d\d\b|\b4\.\d\.\d\b", text):
        return "soft"
    if any(token in text for token in HARD_BOUNCE_HINT_TOKENS):
        return "hard"
    if any(token in text for token in SOFT_BOUNCE_HINT_TOKENS):
        return "soft"
    return "unknown"


def extract_bounced_recipient(msg, body_text):
    body_text = body_text or ""
    m = re.search(r"Final-Recipient:\s*rfc822;\s*([^\s>]+)", body_text, re.I)
    if m:
        return m.group(1).strip().lower()

    m2 = re.search(r"(?:for|to)\s+<?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})>?", body_text, re.I)
    if m2:
        return m2.group(1).strip().lower()

    for part in msg.walk() if msg.is_multipart() else [msg]:
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = decode_fragment(payload)
        m3 = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if m3:
            return m3.group(0).strip().lower()

    return ""

def find_latest_verified_file():
    files = sorted(
        glob(os.path.join(DATA_DIR, "leads_*_NO_WEBSITE_*.csv")) +
        glob(os.path.join(DATA_DIR, "no_website_emails_*_*.csv")),
        reverse=True,
    )
    return files[0] if files else None

def parse_context_from_filename(fname):
    base = os.path.basename(fname)

    m_leads = re.search(r"leads_(.+)_NO_WEBSITE_\d{4}-\d{2}-\d{2}", base)
    if m_leads:
        payload = m_leads.group(1)
        parts = payload.split("_")
        split_idx = None
        for idx, token in enumerate(parts):
            if len(token) == 2 and token.isalpha() and token == token.upper():
                split_idx = idx + 1
                break
        if split_idx and split_idx < len(parts):
            town = " ".join(parts[:split_idx]).replace("__", " ").replace("_", " ").strip()
            service = " ".join(parts[split_idx:]).replace("__", " ").replace("_", " ").strip()
            return town.title(), service

    # Expected pattern: no_website_emails_<town>_<service>_<DATE>.csv
    m = re.search(r"no_website_emails_(.+)_(.+)_\d{4}-\d{2}-\d{2}", base)
    if m:
        town, service = m.groups()
        return town.replace("-", " ").replace("_", " ").title(), service.replace("-", " ").replace("_", " ")
    return "Your Town", "Your Service"


def normalize_text_value(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def score_lead(row, email_field):
    score = 0
    business = normalize_text_value(row.get("name", ""))
    notes = normalize_text_value(row.get("notes", "")).lower()
    website = normalize_text_value(row.get("website", ""))

    if email_field and "@" in email_field:
        score += 1
        domain = email_field.split("@")[-1].lower()
        if domain not in FREE_EMAIL_DOMAINS:
            score += 1

    if len(business.split()) >= 2:
        score += 1

    if website:
        score -= 2

    if any(token in notes for token in ["under construction", "business.site", "no website"]):
        score += 1

    return score


def should_skip_non_business_lead(row, email_field):
    email_field = (email_field or "").strip().lower()
    if "@" in email_field:
        domain = email_field.split("@")[-1]
        if domain.endswith(".gov") or domain.endswith(".edu"):
            return True, "institutional_domain"
        if domain in NON_BUSINESS_RECIPIENT_DOMAINS:
            return True, "non_business_recipient_domain"

    name = normalize_text_value(row.get("name", "")).lower()
    notes = normalize_text_value(row.get("notes", "")).lower()
    link = normalize_text_value(row.get("link", "")).lower()
    website = normalize_text_value(row.get("website", "")).lower()
    text_blob = f"{name} {notes} {link} {website}"

    if any(token in text_blob for token in NON_BUSINESS_TEXT_HINTS):
        return True, "non_business_text_hint"

    source_candidates = [
        normalize_text_value(row.get("link", "")).lower(),
        normalize_text_value(row.get("website", "")).lower(),
    ]
    for src in source_candidates:
        if not src:
            continue
        parsed = urlparse(src)
        src_domain = (parsed.netloc or "").lower().replace("www.", "")
        if any(src_domain == d or src_domain.endswith(f".{d}") for d in NON_BUSINESS_SOURCE_DOMAINS):
            return True, "non_business_source_domain"

    return False, "ok"


def extract_domain_from_url(raw_url):
    raw_url = normalize_text_value(raw_url).lower()
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    domain = (parsed.netloc or "").lower().replace("www.", "")
    return domain


def should_skip_domain_mismatch(row, email_field):
    email_field = (email_field or "").strip().lower()
    if "@" not in email_field:
        return False, "ok"

    recipient_domain = email_field.split("@")[-1]

    website_domain = extract_domain_from_url(row.get("website", ""))
    link_domain = extract_domain_from_url(row.get("link", ""))
    business_domain = website_domain or link_domain
    if not business_domain:
        return False, "ok"

    if recipient_domain == business_domain or recipient_domain.endswith(f".{business_domain}"):
        return False, "ok"

    if business_domain.endswith(f".{recipient_domain}"):
        return False, "ok"

    return True, f"domain_mismatch:{recipient_domain}!={business_domain}"


def build_email_body(business, town, service, contact_name="there"):
    base_template = BODY_TEMPLATE.replace("Hi {business},", "Hi {contact_name},")
    base = base_template.format(
        business=business,
        town=town,
        service=service,
        contact_name=(contact_name or "there"),
    )
    if UNSUBSCRIBE_FOOTER:
        return f"{base}\n\n{UNSUBSCRIBE_FOOTER}"
    return base

# --------------------------------------------------
# Core: send emails
# --------------------------------------------------
def send_cold_emails(csv_file=None):
    sent = load_sent_log()
    suppressed = load_suppression_list()
    already_sent_today = load_daily_sent_count()
    domain_send_counts = load_daily_domain_counts()
    remaining_quota = max(DAILY_EMAIL_TARGET - already_sent_today, 0)

    if remaining_quota <= 0:
        print(f"[INFO] Daily cap reached ({DAILY_EMAIL_TARGET}/{DAILY_EMAIL_TARGET}). Skipping send.")
        return

    csv_file = csv_file or find_latest_verified_file()
    if not csv_file:
        print("[ERR] No verified leads file found.")
        return
    if not os.path.exists(csv_file):
        print(f"[ERR] Provided leads file does not exist: {csv_file}")
        return

    town, service = parse_context_from_filename(csv_file)
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())
    else:
        context = ssl.create_default_context()

    print(f"[INFO] Sending from file: {os.path.basename(csv_file)} ({town}, {service})")
    print(f"[INFO] Daily quota remaining: {remaining_quota}/{DAILY_EMAIL_TARGET}")
    print(f"[INFO] Lead score threshold: {LEAD_SCORE_THRESHOLD}")
    print(f"[INFO] Domain cap: {MAX_EMAILS_PER_DOMAIN} | Block generic inboxes: {BLOCK_GENERIC_INBOXES}")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(EMAIL_ADDR, EMAIL_PASS)

        with open(csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email_field = row.get("emails","").split(",")[0].strip().lower()
                if not email_field or email_field in sent or email_field in suppressed:
                    if email_field in suppressed:
                        print(f"[SUPPRESS] Skipping suppressed address: {email_field}")
                    continue

                if BLOCK_GENERIC_INBOXES and is_generic_inbox(email_field):
                    print(f"[GENERIC] Skipping generic inbox: {email_field}")
                    continue

                if PRE_SEND_VALIDATE_EMAILS:
                    valid, reason = should_send_to_email(email_field)
                    if not valid:
                        print(f"[VALIDATION] Skipping {email_field} ({reason})")
                        continue

                domain = email_field.split("@")[-1]
                if MAX_EMAILS_PER_DOMAIN > 0 and domain_send_counts.get(domain, 0) >= MAX_EMAILS_PER_DOMAIN:
                    print(f"[DOMAIN-CAP] Skipping {email_field} (domain {domain} cap reached)")
                    continue

                should_skip, reason = should_skip_non_business_lead(row, email_field)
                if should_skip:
                    print(f"[QUALITY] Skipping {email_field} ({reason})")
                    continue

                mismatch_skip, mismatch_reason = should_skip_domain_mismatch(row, email_field)
                if mismatch_skip:
                    print(f"[QUALITY] Skipping {email_field} ({mismatch_reason})")
                    continue

                lead_score = score_lead(row, email_field)
                if lead_score < LEAD_SCORE_THRESHOLD:
                    print(f"[SCORE] Skipping {email_field} (score={lead_score}, threshold={LEAD_SCORE_THRESHOLD})")
                    continue

                business = row.get("name","your company").strip()
                subject = random.choice(SUBJECTS).format(business=business)
                contact_name = extract_contact_name(email_field)
                body = build_email_body(
                    business=business,
                    town=town,
                    service=service,
                    contact_name=contact_name,
                )

                msg = MIMEText(body, "plain", "utf-8")
                msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_ADDR, email_field

                try:
                    server.sendmail(EMAIL_ADDR, [email_field], msg.as_string())
                    append_to_log(email_field)
                    append_to_daily_log(email_field)
                    domain_send_counts[domain] = domain_send_counts.get(domain, 0) + 1
                    remaining_quota -= 1
                    print(f"[SENT] {business} → {email_field} | {subject}")
                    if remaining_quota <= 0:
                        print(f"[INFO] Daily cap reached ({DAILY_EMAIL_TARGET}/{DAILY_EMAIL_TARGET}).")
                        break
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
        processed_ids = load_processed_message_ids()

        with open(REPLIES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for i in ids:
                typ, msg_data = mail.fetch(i, "(RFC822)")
                if typ != "OK": continue
                msg = email.message_from_bytes(msg_data[0][1])
                message_id = (msg.get("Message-ID", "") or "").strip()
                if message_id and message_id in processed_ids:
                    continue

                frm = msg.get("From", "")
                subject, enc = decode_header(msg.get("Subject",""))[0]
                subject = decode_fragment(subject)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = decode_fragment(part.get_payload(decode=True)[:1500]).replace("\n"," ")
                            break
                else:
                    body = decode_fragment(msg.get_payload(decode=True))[:1500].replace("\n"," ")

                if is_delivery_status_notification(msg, subject):
                    bounced_email = extract_bounced_recipient(msg, body)
                    bounce_type = classify_bounce_type(subject, body)
                    if bounced_email:
                        if bounce_type == "hard":
                            append_to_suppressions(bounced_email, reason="delivery_failure_hard")
                            print(f"[BOUNCE] Hard bounce suppressed: {bounced_email}")
                        else:
                            print(f"[BOUNCE] {bounce_type} bounce detected: {bounced_email} (not auto-suppressed)")
                    continue

                if is_auto_reply(msg, subject):
                    if message_id:
                        processed_ids.add(message_id)
                        append_processed_message_id(message_id)
                    continue

                if message_id:
                    processed_ids.add(message_id)
                    append_processed_message_id(message_id)

                if any(tok in subject.lower() for tok in ["question", "website", "mobile site", "call"]):
                    body = body[:150]
                    date = msg.get("Date","")
                    writer.writerow([frm, subject, body, date])
                    reply_email = extract_email_address(frm)
                    if reply_email:
                        replied_addresses.add(reply_email)
                        print(f"[REPLY] {reply_email} | {subject}")

                        combined = f"{subject} {body}".lower()
                        if any(keyword in combined for keyword in NEGATIVE_REPLY_KEYWORDS):
                            append_to_suppressions(reply_email, reason="negative_reply")
                            print(f"[SUPPRESS] Added from negative reply: {reply_email}")

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
    target_csv = sys.argv[1] if len(sys.argv) > 1 else None
    send_cold_emails(target_csv)