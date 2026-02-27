#!/usr/bin/env python3
"""
discover_no_website_leads.py
------------------------------------------------------
Improved discovery engine for ZBA Digital (v2026.2.23‑Fixed)

Purpose:
• Identify local service businesses likely NOT to have a real website.
• Output → leads_<city>_<service>_NO_WEBSITE_<date>.csv
• Filters out known directories, working business sites, and social profiles.
------------------------------------------------------
"""

import os
import re
import time
import json
import hashlib
import requests
import pandas as pd
import traceback
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import date, datetime, timedelta

# ======================================================
# ENVIRONMENT SETUP
# ======================================================
load_dotenv()
SERPER = os.getenv("SERPER_API_KEY")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_DIR = os.path.expanduser("~/Scripts/Daily_Leads")
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "7"))
RUN_METRICS_FILE = os.getenv("PIPELINE_RUN_METRICS_FILE", "")

# ======================================================
# AUTO‑ARCHIVE PREVIOUS DATA FILES
# ======================================================
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_old_data():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = os.path.join(ARCHIVE_DIR, timestamp)
    os.makedirs(session_dir, exist_ok=True)
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".csv") and (
            f.startswith("leads_") or f.startswith("no_website_emails_")
        )
    ]
    if not files:
        print("[ARCHIVE] No existing data files to move.")
        return
    for name in files:
        src = os.path.join(DATA_DIR, name)
        dst = os.path.join(session_dir, name)
        try:
            os.rename(src, dst)
        except Exception as e:
            print(f"[ARCHIVE] Could not move {name}: {e}")
    print(f"[ARCHIVE] Moved {len(files)} old data file(s) → {session_dir}")

# Run archive before new discovery session
archive_old_data()

DATESTAMP = datetime.now().strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ZBA-LeadBot/1.0; +https://zbadigital.com)"
}

NON_BUSINESS_DOMAIN_HINTS = {
    "indeed.com", "linkedin.com", "glassdoor.com", "monster.com", "ziprecruiter.com",
    "careerbuilder.com", "simplyhired.com", "wikipedia.org", "wikidata.org", "youtube.com",
    "pinterest.com", "reddit.com", "medium.com", "github.com", "yale.edu", "harvard.edu",
    "stanford.edu", "mit.edu", "nih.gov", "va.gov", "usa.gov", "cdc.gov", "loc.gov",
    "zocdoc.com", "healthgrades.com", "webmd.com", "mapquest.com", "yellowpages.com",
}

NON_BUSINESS_TEXT_HINTS = [
    "[pdf]", "pdf", "jobs", "job", "employment", "salary", "career", "careers",
    "university", "department of", "federal", "government", "wikipedia", "curriculum vitae",
]


def _cache_path(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{prefix}_{digest}.json")


def cache_get(prefix: str, key: str):
    path = _cache_path(prefix, key)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        created = datetime.fromisoformat(payload.get("created_at", "1970-01-01T00:00:00"))
        if datetime.now() - created > timedelta(days=CACHE_TTL_DAYS):
            return None
        return payload.get("value")
    except Exception:
        return None


def cache_set(prefix: str, key: str, value):
    path = _cache_path(prefix, key)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "value": value,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def increment_api_counter(counter_key: str):
    if not RUN_METRICS_FILE:
        return
    try:
        data = {"google_places": 0, "serper": 0, "hunter": 0}
        if os.path.isfile(RUN_METRICS_FILE):
            with open(RUN_METRICS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for key in data:
                data[key] = int(loaded.get(key, 0) or 0)
        if counter_key in data:
            data[counter_key] += 1
        with open(RUN_METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def prune_expired_cache():
    cutoff = datetime.now() - timedelta(days=CACHE_TTL_DAYS)
    removed = 0
    if not os.path.isdir(CACHE_DIR):
        return removed
    for name in os.listdir(CACHE_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            created = datetime.fromisoformat(payload.get("created_at", "1970-01-01T00:00:00"))
            if created < cutoff:
                os.remove(path)
                removed += 1
        except Exception:
            pass
    if removed:
        print(f"[CACHE] Pruned {removed} expired cache file(s).")
    return removed


prune_expired_cache()

# ======================================================
# RETRY WRAPPER
# ======================================================
def retry_request(func, *args, **kwargs):
    """Simple retry wrapper for transient HTTP errors."""
    for attempt in range(2):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            wait = 3 * (attempt + 1)
            print(f"[RETRY] Error: {e} (wait {wait}s)")
            time.sleep(wait)
    print("[ERROR] All retry attempts failed.")
    return None


# ======================================================
# SERPER SEARCH
# ======================================================
def run_serper_search(query: str):
    """Query Serper.dev API for search results."""
    if not SERPER:
        print("[ERROR] SERPER_API_KEY missing in .env.")
        return []

    cached = cache_get("serper", query)
    if cached is not None:
        return cached
    
    def _call():
        increment_api_counter("serper")
        headers = {"X-API-KEY": SERPER, "Content-Type": "application/json"}
        payload = {"q": query, "num": 10}
        resp = requests.post(
            "https://google.serper.dev/search",
            headers=headers, json=payload, timeout=25
        )
        resp.raise_for_status()
        return resp.json().get("organic", [])
    
    result = retry_request(_call) or []
    cache_set("serper", query, result)
    return result


# ======================================================
# HELPER: Check if a link likely represents a real business website
# ======================================================
def is_probably_real_website(link: str, business_name: str = "") -> bool:
    if not link:
        return False
    domain = urlparse(link).netloc.lower().strip()
    if not domain:
        return False

    # Ignore directories or social platforms
    directory_domains = [
        "yelp.com", "yellowpages.com", "mapquest.com", "angi.com", "facebook.com",
        "linkedin.com", "houzz.com", "bbb.org", "thumbtack.com", "homeadvisor.com"
    ]
    if any(d in domain for d in directory_domains):
        return False

    # Keep only "business.site" under Google domains
    if "google.com" in domain and "business.site" not in link:
        return False

    # If the business name appears in the domain, likely a real business site
    clean_name = re.sub(r"[^a-z0-9]", "", business_name.lower())
    clean_domain = re.sub(r"[^a-z0-9]", "", domain.replace("www.", "").split(".")[0])
    if clean_name and clean_name in clean_domain:
        return True

    # Quick probe — is this an actual functional homepage?
    try:
        resp = requests.get(f"http://{domain}", headers=HEADERS, timeout=4)
        if resp.status_code == 200:
            if re.search(r"(home|welcome to|services|about us)", resp.text[:3000], re.I):
                return True
    except Exception:
        pass

    return False


def should_skip_non_business_result(title: str, link: str, snippet: str = "") -> bool:
    title_lower = (title or "").lower()
    snippet_lower = (snippet or "").lower()
    link_lower = (link or "").lower()

    parsed = urlparse(link_lower)
    domain = (parsed.netloc or "").lower().replace("www.", "")
    path = parsed.path or ""

    if domain.endswith(".gov") or domain.endswith(".edu"):
        return True

    if any(domain == d or domain.endswith(f".{d}") for d in NON_BUSINESS_DOMAIN_HINTS):
        return True

    if path.lower().endswith(".pdf"):
        return True

    text_blob = f"{title_lower} {snippet_lower} {link_lower}"
    if any(token in text_blob for token in NON_BUSINESS_TEXT_HINTS):
        return True

    return False


# ======================================================
# MAIN DISCOVERY LOGIC
# ======================================================
def discover(service: str, town: str):
    """Finds local businesses without websites and saves leads to CSV."""
    try:
        print(f"[DISCOVERY] {service.title()} | {town.title()} – Scanning...")

        # Safe filenames
        safe_city = re.sub(r'[^A-Za-z0-9_]+', '_', town.strip())
        safe_service = re.sub(r'[^A-Za-z0-9_]+', '_', service.strip())
        today = date.today().strftime("%Y-%m-%d")

        out_path = os.path.join(
            DATA_DIR,
            f"leads_{safe_city}_{safe_service}_NO_WEBSITE_{today}.csv"
        )

        # Construct search query emphasizing “no website” context
        query = (
            f'"{service}" "{town}" ("no website" OR "no site" OR "site coming soon" '
            f'OR "under construction" OR "Google My Business" OR "business.site") '
            f'-site:facebook.com -site:yelp.com -site:linkedin.com '
            f'-site:bbb.org -site:angi.com -site:thumbtack.com'
        )

        results = run_serper_search(query)
        if not results:
            print(f"[WARN] No discovery results for {town} | {service}")
            return None

        leads = []
        for item in results:
            title = item.get("title", "").strip()
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            if not title or not link:
                continue

            if should_skip_non_business_result(title, link, snippet):
                if DEBUG:
                    print(f"[SKIP-NONBIZ] {title} -> {link}")
                continue

            # Skip if we confirm it’s a functioning website
            if is_probably_real_website(link, title):
                if DEBUG:
                    print(f"[SKIP] Likely real site: {link}")
                continue

            # Skip if snippet already contains a full domain (self‑referential)
            if re.search(r"www\.[a-z0-9\-]+\.(com|net|org|biz)", snippet, re.I):
                continue

            leads.append({
                "name": title,
                "link": link,
                "website": "",
                "email": "",
                "notes": snippet[:200]
            })
            time.sleep(0.5)

        if not leads:
            print(f"[WARN] All potential results had websites for {town} | {service}")
            return None

        # Write safely‑named CSV
        df = pd.DataFrame(leads).drop_duplicates(subset=["name"])
        df.to_csv(out_path, index=False)
        valid_emails = df['email'].notna().sum() if 'email' in df.columns else 0
        print(f"[STATS] Leads discovered: {len(df)} | Emails found: {valid_emails}")
        print(f"[OK] Discovery complete – {len(df)} leads saved → {out_path}")
        return out_path

    except Exception as e:
        print(f"[ERROR] Discovery error for {service} | {town}: {e}")
        traceback.print_exc()
        return None


# ======================================================
# ENTRYPOINT
# ======================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 discover_no_website_leads.py <service> <city>")
    else:
        discover(sys.argv[1], sys.argv[2])