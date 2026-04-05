#!/usr/bin/env python3
"""
send_cold_emails.py — Final Version
------------------------------------------------------
Dynamic cold-email sender with subject rotation,
delay randomization, and reply‑based cleanup.
------------------------------------------------------
"""

import os, smtplib, ssl, csv, time, random, imaplib, email, re, sys
import requests
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
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.config import get_config_bool, get_config_int
from utils.logger import emit_structured_event

load_dotenv(os.path.join(BASE_DIR, ".env"))
EMAIL_ADDR = os.getenv("DAILY_LEAD_EMAIL_SENDER")
EMAIL_PASS = os.getenv("DAILY_LEAD_EMAIL_PASS")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
IMAP_SERVER = "imap.gmail.com"

DATA_ROOT_DIR = os.path.join(BASE_DIR, "data")
DATA_DIR = os.path.join(DATA_ROOT_DIR, "current")
DAILY_SENT_DIR = os.path.join(DATA_DIR, "daily_sent")
SENT_LOG = os.path.join(DATA_DIR, "sent_log.csv")
REPLIES_FILE = os.path.join(DATA_DIR, "replies.csv")
SUPPRESSIONS_FILE = os.path.join(DATA_DIR, "suppressions.csv")
PENDING_LEADS_FILE = os.getenv("PENDING_LEADS_FILE", "")
PROCESSED_REPLY_IDS_FILE = os.path.join(DATA_DIR, "processed_reply_message_ids.csv")
REPLY_NOTIFY_TO = os.getenv("REPLY_NOTIFY_TO", EMAIL_ADDR)
DAILY_EMAIL_TARGET = get_config_int("outreach.daily_email_target", default=50, env_var="DAILY_EMAIL_TARGET")
LEAD_SCORE_THRESHOLD = get_config_int("enrichment.lead_score_threshold", default=2, env_var="LEAD_SCORE_THRESHOLD")
STARTUP_PRIORITY = os.getenv("STARTUP_PRIORITY", "false").strip().lower() in {"1", "true", "yes", "on"}
STARTUP_SCORE_BOOST = int(os.getenv("STARTUP_SCORE_BOOST", "2"))
STARTUP_MAX_AGE_YEARS = int(os.getenv("STARTUP_MAX_AGE_YEARS", "5"))
STARTUP_EXCLUDE_TECH = os.getenv("STARTUP_EXCLUDE_TECH", "true").strip().lower() in {"1", "true", "yes", "on"}
STARTUP_HINT_KEYWORDS = tuple(
    token.strip().lower()
    for token in os.getenv(
        "STARTUP_HINT_KEYWORDS",
        "founded,established,since,newly opened,recently opened,just launched,new business,new company",
    ).split(",")
    if token.strip()
)
STARTUP_TECH_EXCLUDE_KEYWORDS = tuple(
    token.strip().lower()
    for token in os.getenv(
        "STARTUP_TECH_EXCLUDE_KEYWORDS",
        "saas,software,app,platform,ai,ml,machine learning,cloud,devops,fintech,edtech,martech",
    ).split(",")
    if token.strip()
)
PRE_SEND_VALIDATE_EMAILS = get_config_bool("outreach.pre_send_validate_emails", default=True, env_var="PRE_SEND_VALIDATE_EMAILS")
PRE_SEND_WEBSITE_GUARD = os.getenv("PRE_SEND_WEBSITE_GUARD", "false").strip().lower() in {"1", "true", "yes", "on"}
WEBSITE_GUARD_TIMEOUT_SECONDS = max(1.0, float(os.getenv("WEBSITE_GUARD_TIMEOUT_SECONDS", "4")))
MAX_EMAILS_PER_DOMAIN = get_config_int("outreach.max_emails_per_domain", default=2, env_var="MAX_EMAILS_PER_DOMAIN")
BLOCK_GENERIC_INBOXES = os.getenv("BLOCK_GENERIC_INBOXES", "true").strip().lower() in {"1", "true", "yes", "on"}
ALLOW_INFO_INBOX_WHEN_BUSINESS = os.getenv("ALLOW_INFO_INBOX_WHEN_BUSINESS", "true").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in {"1", "true", "yes", "on"}
SKIP_REPLY_CHECK_CLEANUP = os.getenv("SKIP_REPLY_CHECK_CLEANUP", "false").strip().lower() in {"1", "true", "yes", "on"}
STRUCTURED_LOGGING_ENABLED = get_config_bool(
    "logging.structured.enabled", default=True, env_var="STRUCTURED_LOGGING_ENABLED"
)
HARD_BOUNCE_DOMAIN_SUPPRESS_THRESHOLD = max(0, int(os.getenv("HARD_BOUNCE_DOMAIN_SUPPRESS_THRESHOLD", "0")))
AUTO_SUPPRESS_UNKNOWN_BOUNCES = os.getenv("AUTO_SUPPRESS_UNKNOWN_BOUNCES", "false").strip().lower() in {"1", "true", "yes", "on"}
SUPPRESSION_EXEMPT_EMAILS = {
    addr.strip().lower()
    for addr in [
        EMAIL_ADDR,
        REPLY_NOTIFY_TO,
        os.getenv("EMAIL_USER", ""),
        os.getenv("DAILY_LEAD_EMAIL_TO", ""),
    ]
    if (addr or "").strip()
}
SUPPRESSION_EXEMPT_EMAILS.update(
    {
        addr.strip().lower()
        for addr in os.getenv("SUPPRESSION_EXEMPT_EMAILS_EXTRA", "").split(",")
        if addr.strip()
    }
)
INTERNAL_REPLY_IGNORE_EMAILS = set(SUPPRESSION_EXEMPT_EMAILS)
PIPELINE_NOTIFICATION_SUBJECT_PREFIX = "[pipeline]"
UNSUBSCRIBE_FOOTER = os.getenv("UNSUBSCRIBE_FOOTER", "")
TODAY_STAMP = datetime.now().strftime('%Y-%m-%d')
DAILY_SENT_LOG = os.path.join(DAILY_SENT_DIR, f"daily_sent_{TODAY_STAMP}.csv")
LEGACY_DAILY_SENT_LOG = os.path.join(DATA_DIR, f"daily_sent_{TODAY_STAMP}.csv")
ROOT_LEGACY_DAILY_SENT_LOG = os.path.join(DATA_ROOT_DIR, f"daily_sent_{TODAY_STAMP}.csv")
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
    "consumeraffairs.com", "houzz.com", "showmelocal.com", "groups.io",
    "instagram.com", "mail.instagram.com", "facebook.com", "facebookmail.com",
    "linkedin.com", "twitter.com", "x.com", "tiktok.com", "tiktokv.com",
    "pinterest.com", "snapchat.com", "youtube.com", "support.google.com",
    "reddit.com", "whatsapp.com", "discord.com", "telegram.org", "carfax.com",
}
NON_BUSINESS_SOURCE_DOMAINS = {
    "yelp.com", "bbb.org", "homeadvisor.com", "angi.com", "thumbtack.com",
    "zoominfo.com", "manta.com", "wikipedia.org", "wikimedia.org", "fandom.com",
    "indeed.com", "linkedin.com", "yellowpages.com", "mapquest.com", "zocdoc.com",
    "consumeraffairs.com", "houzz.com",
}
NON_BUSINESS_TEXT_HINTS = [
    "[pdf]", "pdf", "jobs", "job", "employment", "salary", "career", "careers",
    "university", "department of", "federal", "government", "wikipedia",
    "directory", "reviews", "top 10", "wiki", "| page",
]
SERVICE_KEYWORDS = [
    ("roof", "roofing"),
    ("plumb", "plumbing"),
    ("hvac", "HVAC"),
    ("heat", "HVAC"),
    ("cool", "HVAC"),
    ("landscap", "landscaping"),
    ("lawn", "landscaping"),
    ("paint", "painting"),
    ("window clean", "window cleaning"),
    ("cleaning", "cleaning"),
    ("floor", "flooring"),
    ("pest", "pest control"),
    ("fence", "fence installation"),
    ("electric", "electrical"),
    ("florist", "floristry"),
    ("massage", "massage therapy"),
]
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GENERIC_LOCAL_PARTS = {
    "info", "admin", "support", "sales", "contact", "office", "hello", "team", "service", "customerservice"
}
MISMATCH_IGNORED_SOURCE_DOMAINS = {
    "google.com", "maps.google.com", "business.site",
}
LIKELY_FIRST_NAMES = {
    "aaron", "adam", "alex", "alexander", "alexis", "alice", "amanda", "amber", "amy", "andrew", "andy",
    "bryan", "colin",
    "anna", "anthony", "ashley", "austin", "ben", "brandon", "brian", "brittany", "cameron", "carol",
    "charles", "chris", "christina", "dan", "daniel", "david", "derek", "diana", "emily", "emma",
    "eric", "ethan", "evan", "frank", "gabriel", "grace", "hannah", "heather", "ian", "jack",
    "jacob", "james", "jason", "jeff", "jen", "jennifer", "jeremy", "jessica", "john", "jon",
    "jordan", "joseph", "josh", "justin", "karen", "kate", "katherine", "kevin", "kyle", "laura",
    "lauren", "linda", "lisa", "mark", "matt", "megan", "michael", "michelle", "mike", "morgan",
    "nancy", "natalie", "nick", "olivia", "pat", "patrick", "paul", "peter", "rachel", "randall",
    "ryan", "samantha", "sam", "sarah", "scott", "sean", "stephanie", "steve", "susan", "thomas",
    "tim", "tyler", "veronica", "victoria", "will", "william", "zach",
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
    "user unknown", "no such user", "mailbox unavailable", "address not found", "invalid recipient",
    "recipientnotfound", "resolver.adr.recipientnotfound", "not found by smtp address lookup",
    "wasn't found at"
]
SOFT_BOUNCE_HINT_TOKENS = [
    "temporarily", "try again later", "deferred", "greylist", "rate limit"
]
MX_CACHE = {}
WEBSITE_GUARD_CACHE = {}
WEBSITE_GUARD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ZBA-LeadBot/1.0; +https://zbadigital.com)"
}

DEFAULT_BLOCKED_RECIPIENT_DOMAINS = {
    "groups.io", "showmelocal.com", "instagram.com", "mail.instagram.com",
    "facebook.com", "facebookmail.com", "linkedin.com", "twitter.com", "x.com",
    "tiktok.com", "tiktokv.com", "youtube.com", "support.google.com", "pinterest.com",
    "snapchat.com", "reddit.com", "whatsapp.com", "discord.com", "telegram.org",
    "carfax.com",
    "mapquest.com", "yellowpages.com",
    "yelp.com", "bbb.org", "angi.com", "thumbtack.com", "homeadvisor.com", "houzz.com",
    "zoominfo.com", "manta.com", "consumeraffairs.com",
}

BLOCKED_RECIPIENT_DOMAINS_EXTRA = {
    d.strip().lower()
    for d in os.getenv("BLOCKED_RECIPIENT_DOMAINS_EXTRA", "").split(",")
    if d.strip()
}
BLOCKED_RECIPIENT_DOMAINS = DEFAULT_BLOCKED_RECIPIENT_DOMAINS | BLOCKED_RECIPIENT_DOMAINS_EXTRA

os.makedirs(DAILY_SENT_DIR, exist_ok=True)

# --------------------------------------------------
# Message templates
# --------------------------------------------------
SUBJECTS = [
    "{business} -- no website showing up on Google",
    "Customers in {town} searching for you can't find you",
    "Found {business} on Google Maps",
    "Quick note for {business}",
    "{contact_name} -- noticed something about {business} online",
    "Missing out on {town} searches?",
    "{business}: your competitors have websites",
]

BODY_TEMPLATE = """Hi {contact_name},

{opener_line}

Without a website, customers searching for {service} in {town} are going straight to your competitors. I build clean, mobile-friendly sites for local businesses -- most go live within a week.

{cta_line}

Would it make sense to connect this week?

Alex
ZBA Digital
www.zbadigital.com
"""

# --------------------------------------------------
# Helper utilities
# --------------------------------------------------
def load_sent_log():
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG, newline="") as f:
        sent = set()
        for row in csv.reader(f):
            if not row:
                continue
            first = (row[0] or "").strip().lower()
            if not first or first == "email":
                continue
            sent.add(first)
        return sent

def append_to_log(email, lead_score="", source_file=""):
    with open(SENT_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            email.lower(),
            lead_score,
            datetime.now().isoformat(timespec="seconds"),
            os.path.basename(source_file or ""),
        ])

def append_to_daily_log(email, lead_score="", source_file=""):
    with open(DAILY_SENT_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            email.lower(),
            lead_score,
            datetime.now().isoformat(timespec="seconds"),
            os.path.basename(source_file or ""),
        ])


def load_pending_rows():
    pending_file = PENDING_LEADS_FILE or os.path.join(DATA_DIR, "pending_leads.csv")
    if not os.path.exists(pending_file):
        return []
    rows = []
    with open(pending_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            email_val = (row.get("emails", "") or "").split(",")[0].strip().lower()
            if not email_val:
                continue
            rows.append(row)
    return rows


def save_pending_rows(rows):
    pending_file = PENDING_LEADS_FILE or os.path.join(DATA_DIR, "pending_leads.csv")
    rows = rows or []
    if not rows:
        default_fields = [
            "name", "emails", "notes", "website", "link",
            "lead_score", "__source_file", "__town", "__service", "__queued_at",
        ]
        with open(pending_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=default_fields)
            writer.writeheader()
        return

    merged_fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in merged_fieldnames:
                merged_fieldnames.append(key)

    with open(pending_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=merged_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in merged_fieldnames})


def build_pending_row(row, source_file="", town="", service="", lead_score=""):
    pending_row = dict(row or {})
    pending_row["__source_file"] = source_file or pending_row.get("__source_file", "")
    pending_row["__town"] = town or pending_row.get("__town", "")
    pending_row["__service"] = service or pending_row.get("__service", "")
    if lead_score != "":
        pending_row["lead_score"] = lead_score
    pending_row.pop("__skip_reason", None)
    pending_row["__queued_at"] = datetime.now().isoformat(timespec="seconds")
    return pending_row

def load_suppression_list():
    if not os.path.exists(SUPPRESSIONS_FILE):
        return set()
    with open(SUPPRESSIONS_FILE, newline="", encoding="utf-8") as f:
        rows = csv.reader(f)
        return set(row[0].strip().lower() for row in rows if row and row[0].strip())

def append_to_suppressions(email_addr, reason="manual"):
    email_addr = (email_addr or "").strip().lower()
    if not email_addr:
        return False
    if email_addr in SUPPRESSION_EXEMPT_EMAILS:
        return False
    existing = load_suppression_list()
    if email_addr in existing:
        return False
    with open(SUPPRESSIONS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([email_addr, reason, datetime.now().isoformat(timespec="seconds")])
    return True


def load_hard_bounce_domain_blocklist(threshold):
    threshold = max(0, int(threshold or 0))
    if threshold <= 0 or not os.path.exists(SUPPRESSIONS_FILE):
        return set()

    counts = {}
    with open(SUPPRESSIONS_FILE, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            suppressed_email = (row[0] or "").strip().lower()
            reason = (row[1] or "").strip().lower()
            if reason != "delivery_failure_hard":
                continue
            if "@" not in suppressed_email:
                continue
            domain = suppressed_email.split("@", 1)[1].strip().lower()
            if not domain:
                continue
            counts[domain] = counts.get(domain, 0) + 1

    return {domain for domain, count in counts.items() if count >= threshold}

def extract_email_address(from_field):
    m = re.search(r"<([^>]+)>", from_field or "")
    if m:
        return m.group(1).strip().lower()
    m2 = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", from_field or "")
    return m2.group(0).strip().lower() if m2 else ""

def load_daily_sent_count():
    if os.path.exists(DAILY_SENT_LOG):
        active_log = DAILY_SENT_LOG
    elif os.path.exists(LEGACY_DAILY_SENT_LOG):
        active_log = LEGACY_DAILY_SENT_LOG
    else:
        active_log = ROOT_LEGACY_DAILY_SENT_LOG
    if not os.path.exists(active_log):
        return 0
    try:
        with open(active_log, newline="") as f:
            return sum(1 for _ in csv.reader(f))
    except Exception:
        return 0


def load_daily_domain_counts():
    counts = {}
    if os.path.exists(DAILY_SENT_LOG):
        active_log = DAILY_SENT_LOG
    elif os.path.exists(LEGACY_DAILY_SENT_LOG):
        active_log = LEGACY_DAILY_SENT_LOG
    else:
        active_log = ROOT_LEGACY_DAILY_SENT_LOG
    if not os.path.exists(active_log):
        return counts
    try:
        with open(active_log, newline="", encoding="utf-8") as f:
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


def should_allow_generic_business_inbox(row, email_addr):
    if not ALLOW_INFO_INBOX_WHEN_BUSINESS:
        return False

    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return False

    local_part, domain = email_addr.split("@", 1)
    if local_part != "info":
        return False
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return False
    if domain.endswith(".gov") or domain.endswith(".edu"):
        return False
    if domain in NON_BUSINESS_RECIPIENT_DOMAINS:
        return False

    business_name = normalize_text_value(row.get("name", "")).lower()
    if not business_name:
        return False
    root = domain.split(".")[0]
    root_clean = re.sub(r"[^a-z0-9]", "", root)
    name_clean = re.sub(r"[^a-z0-9]", "", business_name)
    if not root_clean or not name_clean:
        return False
    if root_clean not in name_clean and name_clean not in root_clean:
        return False

    skip_non_biz, _ = should_skip_non_business_lead(row, email_addr)
    if skip_non_biz:
        return False

    mismatch_skip, _ = should_skip_domain_mismatch(row, email_addr)
    if mismatch_skip:
        return False

    return True


def extract_contact_name(email_addr):
    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return "there"
    local_part = email_addr.split("@")[0]
    parts = [part.strip() for part in re.split(r"[._+\-]", local_part) if part.strip()]
    if not parts:
        return "there"
    token = parts[0]
    if len(parts) == 1 and token not in LIKELY_FIRST_NAMES:
        return "there"
    if not token or token in GENERIC_LOCAL_PARTS:
        return "there"
    if not token.isalpha() or len(token) < 2:
        return "there"
    return token.capitalize()


def build_subject_line(business, contact_name, town):
    contact_name = (contact_name or "there").strip()
    templates = SUBJECTS
    if contact_name.lower() == "there":
        templates = [template for template in SUBJECTS if "{contact_name}" not in template]
    template = random.choice(templates or SUBJECTS)
    return template.format(
        business=business,
        contact_name=contact_name,
        town=format_town_for_copy(town),
    )


def build_ssl_context():
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()

def remove_from_log(replied_emails):
    if not os.path.exists(SENT_LOG):
        return

    replied = {
        (email_addr or "").strip().lower()
        for email_addr in (replied_emails or [])
        if (email_addr or "").strip()
    }
    if not replied:
        return

    rows_to_keep = []
    with open(SENT_LOG, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            email_addr = (row[0] or "").strip().lower()
            if email_addr in replied:
                continue
            rows_to_keep.append(row)

    with open(SENT_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows_to_keep)


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


def extract_reply_excerpt(body_text):
    body_text = decode_fragment(body_text or "")
    if not body_text:
        return ""

    # Ignore quoted thread content and keep only the newest reply section.
    split_markers = [
        "\nOn ",
        "\nFrom:",
        "\nVon:",
        "\n-----Original Message-----",
    ]
    excerpt = body_text
    for marker in split_markers:
        idx = excerpt.find(marker)
        if idx != -1:
            excerpt = excerpt[:idx]
    return excerpt.strip()


def is_negative_reply_text(subject, body_text):
    excerpt = extract_reply_excerpt(body_text)
    combined = f"{subject or ''} {excerpt}".lower()
    return any(keyword in combined for keyword in NEGATIVE_REPLY_KEYWORDS)


def should_ignore_reply_message(reply_email, subject):
    reply_email = (reply_email or "").strip().lower()
    subject_lower = (subject or "").strip().lower()

    if reply_email and reply_email in INTERNAL_REPLY_IGNORE_EMAILS:
        return True

    if subject_lower.startswith(PIPELINE_NOTIFICATION_SUBJECT_PREFIX):
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


def has_live_business_website(domain):
    clean_domain = (domain or "").strip().lower().replace("www.", "")
    if not clean_domain or "." not in clean_domain:
        return False
    if clean_domain.endswith(".gov") or clean_domain.endswith(".edu"):
        return False
    if domain_matches_any(clean_domain, NON_BUSINESS_RECIPIENT_DOMAINS):
        return False
    if domain_matches_any(clean_domain, BLOCKED_RECIPIENT_DOMAINS):
        return False

    if clean_domain in WEBSITE_GUARD_CACHE:
        return WEBSITE_GUARD_CACHE[clean_domain]

    for candidate in (f"https://{clean_domain}", f"http://{clean_domain}"):
        try:
            resp = requests.get(
                candidate,
                headers=WEBSITE_GUARD_HEADERS,
                timeout=WEBSITE_GUARD_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            if 200 <= resp.status_code < 400:
                content_type = (resp.headers.get("Content-Type", "") or "").lower()
                body = (resp.text or "")[:3000]
                if "html" in content_type or re.search(r"<html|<!doctype", body, re.I):
                    WEBSITE_GUARD_CACHE[clean_domain] = True
                    return True
        except Exception:
            continue

    WEBSITE_GUARD_CACHE[clean_domain] = False
    return False


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
    if re.search(r"\b5\d\d\b|\b5\.\d\.\d+\b", text):
        return "hard"
    if re.search(r"\b4\d\d\b|\b4\.\d\.\d+\b", text):
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


def handle_bounce_event(bounced_email, bounce_type, seen_bounce_events=None):
    bounced_email = (bounced_email or "").strip().lower()
    bounce_type = (bounce_type or "unknown").strip().lower() or "unknown"
    if not bounced_email:
        return False

    event_key = (bounce_type, bounced_email)
    if seen_bounce_events is not None and event_key in seen_bounce_events:
        return False
    if seen_bounce_events is not None:
        seen_bounce_events.add(event_key)

    if bounce_type == "hard":
        added = append_to_suppressions(bounced_email, reason="delivery_failure_hard")
        if added is not False:
            print(f"[BOUNCE] Hard bounce suppressed: {bounced_email}")
        else:
            print(f"[BOUNCE] Hard bounce detected: {bounced_email} (suppression skipped)")
    elif bounce_type == "unknown" and AUTO_SUPPRESS_UNKNOWN_BOUNCES:
        added = append_to_suppressions(bounced_email, reason="delivery_failure_unknown")
        if added is not False:
            print(f"[BOUNCE] Unknown bounce suppressed: {bounced_email}")
        else:
            print(f"[BOUNCE] unknown bounce detected: {bounced_email} (suppression skipped)")
    else:
        print(f"[BOUNCE] {bounce_type} bounce detected: {bounced_email} (not auto-suppressed)")
    return True

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

    if STARTUP_PRIORITY:
        score += startup_signal_score(row, email_field)

    return score


def startup_signal_score(row, email_field=""):
    score = 0
    fields = [
        normalize_text_value(row.get("name", "")),
        normalize_text_value(row.get("notes", "")),
        normalize_text_value(row.get("link", "")),
        normalize_text_value(row.get("website", "")),
    ]
    blob = " ".join(fields).lower()

    if STARTUP_EXCLUDE_TECH and STARTUP_TECH_EXCLUDE_KEYWORDS:
        if any(token in blob for token in STARTUP_TECH_EXCLUDE_KEYWORDS):
            return 0

    # Prefer age-based startup detection over industry/TLD heuristics.
    current_year = datetime.now().year
    year_match = re.search(r"\\b(?:founded|est\\.?|established|since)\\s*(?:in\\s*)?(19\\d{2}|20\\d{2})\\b", blob)
    age_match = False
    if year_match:
        founded_year = int(year_match.group(1))
        age_years = current_year - founded_year
        if 0 <= age_years <= max(0, STARTUP_MAX_AGE_YEARS):
            age_match = True
            score += 1

    young_phrase_match = bool(re.search(r"\\bnewly opened|recently opened|just launched|new business|new company\\b", blob))
    if young_phrase_match:
        score += 1

    # Optional custom hints only count when paired with a young-age signal.
    if STARTUP_HINT_KEYWORDS and any(token in blob for token in STARTUP_HINT_KEYWORDS):
        if age_match or young_phrase_match:
            score += 1

    if score <= 0:
        return 0
    return max(0, STARTUP_SCORE_BOOST)


def should_skip_non_business_lead(row, email_field):
    email_field = (email_field or "").strip().lower()
    if "@" in email_field:
        domain = email_field.split("@")[-1]
        if domain.endswith(".gov") or domain.endswith(".edu"):
            return True, "institutional_domain"
        if domain_matches_any(domain, NON_BUSINESS_RECIPIENT_DOMAINS):
            return True, "non_business_recipient_domain"
        if domain_matches_any(domain, BLOCKED_RECIPIENT_DOMAINS):
            return True, "blocked_recipient_domain"

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


def domain_matches_any(domain, domain_set):
    domain = (domain or "").strip().lower().replace("www.", "")
    if not domain:
        return False
    for blocked in domain_set:
        blocked = (blocked or "").strip().lower()
        if not blocked:
            continue
        if domain == blocked or domain.endswith(f".{blocked}"):
            return True
    return False


def business_name_matches_domain(business_name, domain):
    business = normalize_text_value(business_name).lower()
    clean_domain = (domain or "").strip().lower().replace("www.", "")
    if not business or not clean_domain:
        return False

    root = clean_domain.split(".", 1)[0]
    root_alnum = re.sub(r"[^a-z0-9]", "", root)
    if not root_alnum:
        return False

    business_alnum = re.sub(r"[^a-z0-9]", "", business)
    business_alnum = re.sub(r"(llc|inc|corp|corporation|co|company)$", "", business_alnum)
    if len(business_alnum) >= 6 and (business_alnum in root_alnum or root_alnum in business_alnum):
        return True

    stopwords = {
        "the", "and", "llc", "inc", "co", "corp", "corporation", "company",
        "services", "service",
    }
    tokens = [
        tok for tok in re.findall(r"[a-z0-9]+", business)
        if len(tok) >= 3 and tok not in stopwords
    ]
    token_hits = sum(1 for tok in tokens if tok in root_alnum)
    return token_hits >= 2


def should_apply_pre_send_website_guard(row, email_field):
    email_field = (email_field or "").strip().lower()
    if "@" not in email_field:
        return False

    recipient_domain = email_field.split("@", 1)[1]
    if not recipient_domain:
        return False

    # Apply guard when recipient domain plausibly belongs to this business.
    if business_name_matches_domain(row.get("name", ""), recipient_domain):
        return True

    website_domain = extract_domain_from_url(row.get("website", ""))
    link_domain = extract_domain_from_url(row.get("link", ""))
    for source_domain in (website_domain, link_domain):
        if not source_domain:
            continue
        if source_domain in MISMATCH_IGNORED_SOURCE_DOMAINS:
            continue
        if recipient_domain == source_domain or recipient_domain.endswith(f".{source_domain}"):
            return True
        if source_domain.endswith(f".{recipient_domain}"):
            return True

    return False


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

    if (
        any(business_domain == d or business_domain.endswith(f".{d}") for d in NON_BUSINESS_SOURCE_DOMAINS)
        or any(business_domain == d or business_domain.endswith(f".{d}") for d in MISMATCH_IGNORED_SOURCE_DOMAINS)
    ):
        return False, "ok"

    if recipient_domain == business_domain or recipient_domain.endswith(f".{business_domain}"):
        return False, "ok"

    if business_domain.endswith(f".{recipient_domain}"):
        return False, "ok"

    return True, f"domain_mismatch:{recipient_domain}!={business_domain}"


def format_town_for_copy(town):
    town = normalize_text_value(town)
    if not town:
        return "your area"
    if re.search(r",\s*[A-Za-z]{2}$", town):
        return town
    parts = town.split()
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return f"{' '.join(parts[:-1])}, {parts[-1].upper()}"
    return town


def infer_service_from_row(row, fallback_service=""):
    fallback_service = normalize_text_value(fallback_service)
    fields = [
        normalize_text_value(row.get("name", "")),
        normalize_text_value(row.get("notes", "")),
        normalize_text_value(row.get("link", "")),
        normalize_text_value(row.get("website", "")),
    ]
    blob = " ".join(fields).lower()

    for token, label in SERVICE_KEYWORDS:
        if token in blob:
            return label

    return fallback_service


def resolve_row_context(row, fallback_town, fallback_service):
    row_town = normalize_text_value(row.get("__town", ""))
    row_service = normalize_text_value(row.get("__service", ""))
    if row_town and row_service:
        return row_town, row_service

    source_file = normalize_text_value(row.get("__source_file", ""))
    if source_file:
        source_town, source_service = parse_context_from_filename(source_file)
        if not row_town and source_town and source_town != "Your Town":
            row_town = source_town
        if not row_service and source_service and source_service != "Your Service":
            row_service = source_service

    if not row_town:
        row_town = fallback_town
    if not row_service:
        row_service = fallback_service
    return row_town, row_service


def build_personalized_opener(notes, service, business=""):
    notes_text = normalize_text_value(notes)
    if notes_text:
        compact = re.sub(r"\s+", " ", notes_text).strip()
        compact = re.sub(r"https?://\S+", "", compact).strip()
        first_sentence = re.split(r"[.!?]", compact)[0].strip(" -,:;")
        if len(first_sentence) >= 16:
            sentence_lower = first_sentence.lower()
            low_signal_tokens = [
                "image", "photo", "logo", "banner", "above", "with ocean view",
                "stock", "vector", "wallpaper", "freepik", "shutterstock",
                "directory", "reviews", "marketplace", "products", "services", "venue",
            ]
            high_signal_tokens = [
                "serving", "specializ", "family", "licensed", "insured", "years",
                "since", "locally", "owned", "residential", "commercial", "reviews",
            ]
            has_high_signal = any(token in sentence_lower for token in high_signal_tokens)
            has_low_signal = any(token in sentence_lower for token in low_signal_tokens)
            if has_low_signal or not has_high_signal:
                first_sentence = ""

        if len(first_sentence) >= 16:
            if len(first_sentence) > 100:
                first_sentence = first_sentence[:100].rstrip() + "…"
            return f"Noticed {first_sentence[0].lower() + first_sentence[1:]}."

    business_text = clean_business_name(business)
    if business_text and business_text != "your company":
        return f"I looked up {business_text} on Google Maps and noticed there's no website linked -- that's a lot of potential customers you're missing."

    service_text = normalize_text_value(service).replace("/", " and ")
    service_text = re.sub(r"\s+", " ", service_text).strip().lower()
    service_phrase = service_text
    if "roof" in service_text:
        service_phrase = "roofing"
    elif "plumb" in service_text:
        service_phrase = "plumbing"
    elif "hvac" in service_text:
        service_phrase = "HVAC"
    if service_text:
        return f"I had a quick website idea for local {service_phrase} businesses."
    return "I had a quick website idea for your business."


def infer_business_name_from_email(email_addr):
    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return ""

    domain = email_addr.split("@")[-1].strip().lower()
    if not domain:
        return ""

    core = domain.split(".")[0]
    if not core:
        return ""

    explicit_map = {
        "allenthomasgroup": "Allen Thomas Group",
        "jazzhouse": "Jazz House",
        "sturmelevator": "Sturm Elevator",
        "mccowngordon": "McCown Gordon",
        "zoominfo": "ZoomInfo",
        "homeadvisor": "HomeAdvisor",
        "consumeraffairs": "ConsumerAffairs",
        "owenscorning": "Owens Corning",
        "yelp": "Yelp",
        "bbb": "BBB",
    }
    if core in explicit_map:
        return explicit_map[core]

    normalized = core.replace("-", " ").replace("_", " ")
    return " ".join(token.capitalize() for token in normalized.split() if token).strip()


def clean_business_name(raw_name, recipient_email=""):
    name = normalize_text_value(raw_name)
    for separator in [" | ", " - ", " — "]:
        if separator in name:
            name = name.split(separator)[0].strip()
            break

    if ":" in name:
        left, right = name.split(":", 1)
        right_lower = right.lower()
        if any(token in right_lower for token in [" in ", " near ", "best ", "top ", "reviews", "yelp", "angi", "homeadvisor"]):
            name = left.strip()

    name = re.sub(r"\s+", " ", name).strip(" ,;:")

    # Split common glued suffixes (e.g., allenthomasgroup -> Allen Thomas Group)
    if name and " " not in name and name.lower().isalnum():
        lower_name = name.lower()
        suffixes = ["group", "elevator", "roofing", "plumbing", "electric", "construction", "digital", "services", "solutions"]
        for suffix in suffixes:
            if lower_name.endswith(suffix) and len(lower_name) > len(suffix) + 2:
                prefix = lower_name[: -len(suffix)]
                name = f"{prefix.capitalize()} {suffix.capitalize()}"
                break

    if name:
        return name

    inferred = infer_business_name_from_email(recipient_email)
    return inferred or "your company"


def build_service_cta_line(service):
    return "You can see examples of my work at zbadigital.com/portfolio -- happy to build you a free mockup."


def build_email_body(business, town, service, contact_name="there", notes=""):
    base = BODY_TEMPLATE.format(
        business=business,
        town=format_town_for_copy(town),
        service=service,
        contact_name=(contact_name or "there"),
        opener_line=build_personalized_opener(notes, service, business=business),
        cta_line=build_service_cta_line(service),
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
    hard_bounce_blocked_domains = load_hard_bounce_domain_blocklist(HARD_BOUNCE_DOMAIN_SUPPRESS_THRESHOLD)
    pending_rows = load_pending_rows()
    already_sent_today = load_daily_sent_count()
    domain_send_counts = load_daily_domain_counts()
    remaining_quota = max(DAILY_EMAIL_TARGET - already_sent_today, 0)

    if remaining_quota <= 0:
        print(f"[INFO] Daily cap reached ({DAILY_EMAIL_TARGET}/{DAILY_EMAIL_TARGET}). Skipping send.")
        emit_structured_event(
            "outreach_skipped_daily_cap",
            enabled=STRUCTURED_LOGGING_ENABLED,
            daily_email_target=DAILY_EMAIL_TARGET,
        )
        return

    csv_file = csv_file or find_latest_verified_file()
    if not csv_file:
        print("[ERR] No verified leads file found.")
        return
    if not os.path.exists(csv_file):
        print(f"[ERR] Provided leads file does not exist: {csv_file}")
        return

    town, service = parse_context_from_filename(csv_file)
    context = build_ssl_context()

    print(f"[INFO] Sending from file: {os.path.basename(csv_file)} ({town}, {service})")
    print(f"[INFO] Daily quota remaining: {remaining_quota}/{DAILY_EMAIL_TARGET}")
    print(f"[INFO] Lead score threshold: {LEAD_SCORE_THRESHOLD}")
    print(f"[INFO] Domain cap: {MAX_EMAILS_PER_DOMAIN} | Block generic inboxes: {BLOCK_GENERIC_INBOXES}")
    if pending_rows:
        print(f"[INFO] Pending queue available: {len(pending_rows)} leads")
    if hard_bounce_blocked_domains:
        print(
            f"[INFO] Hard-bounce domain blocklist active: {len(hard_bounce_blocked_domains)} "
            f"domain(s), threshold={HARD_BOUNCE_DOMAIN_SUPPRESS_THRESHOLD}"
        )
    if DRY_RUN:
        print("[INFO] Sender DRY_RUN enabled: previewing emails without SMTP send.")

    emit_structured_event(
        "outreach_start",
        enabled=STRUCTURED_LOGGING_ENABLED,
        csv_file=csv_file,
        town=town,
        service=service,
        daily_email_target=DAILY_EMAIL_TARGET,
        remaining_quota=remaining_quota,
        dry_run=DRY_RUN,
    )

    current_rows = []
    with open(csv_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not row:
                continue
            current_row = dict(row)
            current_row["__source_file"] = csv_file
            current_row["__town"] = town
            current_row["__service"] = service
            current_rows.append(current_row)

    combined_rows = []
    seen_emails = set()
    for row in pending_rows + current_rows:
        email_field = (row.get("emails", "") or "").split(",")[0].strip().lower()
        if not email_field:
            continue
        if email_field in seen_emails:
            continue
        seen_emails.add(email_field)
        row["__lead_score"] = score_lead(row, email_field)
        combined_rows.append(row)

    # Highest quality first: prioritize candidates with stronger lead_score.
    combined_rows.sort(key=lambda item: int(item.get("__lead_score", -999999)), reverse=True)

    carryover_rows = []

    def process_rows(server=None):
        nonlocal remaining_quota
        for row in combined_rows:
            email_field = (row.get("emails", "") or "").split(",")[0].strip().lower()
            row_town, row_service_ctx = resolve_row_context(row, town, service)
            domain = email_field.split("@", 1)[1] if "@" in email_field else ""

            if domain and domain in hard_bounce_blocked_domains:
                print(f"[SUPPRESS-DOMAIN] Skipping {email_field} (domain hard-bounce threshold reached)")
                continue

            if not email_field or email_field in sent or email_field in suppressed:
                if email_field in suppressed:
                    print(f"[SUPPRESS] Skipping suppressed address: {email_field}")
                continue

            website_val = row.get("website", "")
            existing_website = "" if pd.isna(website_val) else str(website_val).strip()
            if existing_website:
                print(f"[WEBSITE] Skipping {email_field} (existing website: {existing_website})")
                continue

            if BLOCK_GENERIC_INBOXES and is_generic_inbox(email_field):
                if should_allow_generic_business_inbox(row, email_field):
                    print(f"[GENERIC-ALLOW] Allowing business info inbox: {email_field}")
                else:
                    print(f"[GENERIC] Skipping generic inbox: {email_field}")
                    continue

            if PRE_SEND_VALIDATE_EMAILS:
                valid, reason = should_send_to_email(email_field)
                if not valid:
                    print(f"[VALIDATION] Skipping {email_field} ({reason})")
                    continue

            if MAX_EMAILS_PER_DOMAIN > 0 and domain_send_counts.get(domain, 0) >= MAX_EMAILS_PER_DOMAIN:
                print(f"[DOMAIN-CAP] Deferring {email_field} (domain {domain} cap reached)")
                if not DRY_RUN:
                    carryover_rows.append(
                        build_pending_row(
                            row,
                            source_file=csv_file,
                            town=row_town,
                            service=row_service_ctx,
                            lead_score=row.get("__lead_score", ""),
                        )
                    )
                continue

            should_skip, reason = should_skip_non_business_lead(row, email_field)
            if should_skip:
                print(f"[QUALITY] Skipping {email_field} ({reason})")
                continue

            mismatch_skip, mismatch_reason = should_skip_domain_mismatch(row, email_field)
            if mismatch_skip:
                print(f"[QUALITY] Skipping {email_field} ({mismatch_reason})")
                continue

            if (
                PRE_SEND_WEBSITE_GUARD
                and domain
                and should_apply_pre_send_website_guard(row, email_field)
                and has_live_business_website(domain)
            ):
                print(f"[WEBSITE-GUARD] Skipping {email_field} (live website detected for domain {domain})")
                continue

            lead_score = score_lead(row, email_field)
            row["__lead_score"] = lead_score
            if lead_score < LEAD_SCORE_THRESHOLD:
                print(f"[SCORE] Skipping {email_field} (score={lead_score}, threshold={LEAD_SCORE_THRESHOLD})")
                continue

            if not DRY_RUN and remaining_quota <= 0:
                carryover_rows.append(
                    build_pending_row(
                        row,
                        source_file=csv_file,
                        town=row_town,
                        service=row_service_ctx,
                        lead_score=lead_score,
                    )
                )
                continue

            business = clean_business_name(row.get("name", ""), recipient_email=email_field)
            contact_name = extract_contact_name(email_field)
            subject = build_subject_line(business=business, contact_name=contact_name, town=row_town)
            lead_service = infer_service_from_row(row, row_service_ctx)
            body = build_email_body(
                business=business,
                town=row_town,
                service=lead_service,
                contact_name=contact_name,
                notes=row.get("notes", ""),
            )

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_ADDR, email_field

            if DRY_RUN:
                body_preview = "\n".join(body.splitlines()[:8])
                print(f"[DRY-SEND] {business} → {email_field} | score={lead_score} | {subject}")
                print(f"[DRY-BODY]\n{body_preview}\n---")
                domain_send_counts[domain] = domain_send_counts.get(domain, 0) + 1
                remaining_quota -= 1
                if remaining_quota <= 0:
                    print(f"[INFO] Daily cap reached ({DAILY_EMAIL_TARGET}/{DAILY_EMAIL_TARGET}).")
                    break
                continue

            try:
                sent_ok = False
                last_send_exc = None
                for attempt in range(3):
                    try:
                        server.sendmail(EMAIL_ADDR, [email_field], msg.as_string())
                        sent_ok = True
                        break
                    except Exception as send_exc:
                        last_send_exc = send_exc
                        print(f"[ERROR] SMTP send failed attempt {attempt + 1}/3 for {email_field}: {send_exc}")
                        if attempt < 2:
                            time.sleep(3 ** attempt)

                if not sent_ok and last_send_exc is not None:
                    raise last_send_exc

                append_to_log(email_field, lead_score=lead_score, source_file=csv_file)
                append_to_daily_log(email_field, lead_score=lead_score, source_file=csv_file)
                sent.add(email_field)
                domain_send_counts[domain] = domain_send_counts.get(domain, 0) + 1
                remaining_quota -= 1
                print(f"[SENT] {business} → {email_field} | score={lead_score} | {subject}")
                if remaining_quota <= 0:
                    print(f"[INFO] Daily cap reached ({DAILY_EMAIL_TARGET}/{DAILY_EMAIL_TARGET}).")
                time.sleep(random.uniform(1,5))
            except Exception as e:
                print(f"[ERR] {email_field}: {e}")
                carryover_rows.append(
                    build_pending_row(
                        row,
                        source_file=csv_file,
                        town=row_town,
                        service=row_service_ctx,
                        lead_score=lead_score,
                    )
                )

    if DRY_RUN:
        process_rows(server=None)
    else:
        smtp_batch_ok = False
        last_smtp_exc = None
        for attempt in range(3):
            try:
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                    server.login(EMAIL_ADDR, EMAIL_PASS)
                    process_rows(server=server)
                smtp_batch_ok = True
                break
            except Exception as smtp_exc:
                last_smtp_exc = smtp_exc
                print(f"[ERROR] SMTP session setup/send failed attempt {attempt + 1}/3: {smtp_exc}")
                if attempt < 2:
                    time.sleep(3 ** attempt)

        if not smtp_batch_ok and last_smtp_exc is not None:
            raise last_smtp_exc

    if not DRY_RUN:
        deduped_pending = []
        seen_pending_emails = set()
        for row in carryover_rows:
            email_field = (row.get("emails", "") or "").split(",")[0].strip().lower()
            if not email_field or email_field in seen_pending_emails:
                continue
            seen_pending_emails.add(email_field)
            deduped_pending.append(row)
        save_pending_rows(deduped_pending)
        print(f"[PENDING] Saved {len(deduped_pending)} lead(s) for future runs.")

    print("[INFO] Outbound cold-email batch finished.\n")
    emit_structured_event(
        "outreach_complete",
        enabled=STRUCTURED_LOGGING_ENABLED,
        csv_file=csv_file,
        dry_run=DRY_RUN,
        remaining_quota=remaining_quota,
        pending_saved=0 if DRY_RUN else len(carryover_rows),
    )
    if DRY_RUN:
        print("[INFO] Sender DRY_RUN: skipping reply-check cleanup.")
        return
    if SKIP_REPLY_CHECK_CLEANUP:
        print("[INFO] SKIP_REPLY_CHECK_CLEANUP enabled: skipping reply-check cleanup.")
        return

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
        seen_bounce_events = set()

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
                            body = decode_fragment(part.get_payload(decode=True)[:1500])
                            break
                else:
                    body = decode_fragment(msg.get_payload(decode=True))[:1500]

                compact_body = re.sub(r"\s+", " ", body).strip()

                if is_delivery_status_notification(msg, subject):
                    bounced_email = extract_bounced_recipient(msg, body)
                    bounce_type = classify_bounce_type(subject, body)
                    if message_id:
                        processed_ids.add(message_id)
                        append_processed_message_id(message_id)
                    if bounced_email:
                        handle_bounce_event(bounced_email, bounce_type, seen_bounce_events=seen_bounce_events)
                    continue

                if is_auto_reply(msg, subject):
                    if message_id:
                        processed_ids.add(message_id)
                        append_processed_message_id(message_id)
                    continue

                if message_id:
                    processed_ids.add(message_id)
                    append_processed_message_id(message_id)

                reply_email = extract_email_address(frm)
                if should_ignore_reply_message(reply_email, subject):
                    continue
                is_negative = bool(reply_email and is_negative_reply_text(subject, body))

                if is_negative:
                    date = msg.get("Date", "")
                    writer.writerow([frm, subject, compact_body[:150], date])
                    replied_addresses.add(reply_email)
                    if append_to_suppressions(reply_email, reason="negative_reply"):
                        print(f"[SUPPRESS] Added from negative reply: {reply_email}")
                    else:
                        print(f"[SUPPRESS] Skipped exempt/duplicate negative reply: {reply_email}")
                    continue

                if any(tok in subject.lower() for tok in ["question", "website", "mobile site", "call"]):
                    date = msg.get("Date", "")
                    writer.writerow([frm, subject, compact_body[:150], date])
                    if reply_email:
                        replied_addresses.add(reply_email)
                        print(f"[REPLY] {reply_email} | {subject}")

        mail.logout()
        if replied_addresses:
            send_reply_notifications(replied_addresses)
        return replied_addresses
    except Exception as e:
        print("[ERR] Reply check failed:", e)
        emit_structured_event(
            "reply_check_error",
            enabled=STRUCTURED_LOGGING_ENABLED,
            error=str(e),
        )
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

        context = build_ssl_context()
        notify_ok = False
        last_notify_exc = None
        for attempt in range(3):
            try:
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as s:
                    s.login(EMAIL_ADDR, EMAIL_PASS)
                    s.sendmail(EMAIL_ADDR, [REPLY_NOTIFY_TO], msg.as_string())
                notify_ok = True
                break
            except Exception as smtp_exc:
                last_notify_exc = smtp_exc
                print(f"[ERROR] SMTP reply notification failed attempt {attempt + 1}/3: {smtp_exc}")
                if attempt < 2:
                    time.sleep(3 ** attempt)

        if not notify_ok and last_notify_exc is not None:
            raise last_notify_exc

        print(f"[NOTIFY] Sent reply summary to {REPLY_NOTIFY_TO}")
    except Exception as e:
        print("[ERR] Reply notification failed:", e)

# --------------------------------------------------
if __name__ == "__main__":
    target_csv = sys.argv[1] if len(sys.argv) > 1 else None
    send_cold_emails(target_csv)