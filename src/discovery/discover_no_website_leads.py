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
import sys
import requests
import pandas as pd
import traceback
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import date, datetime, timedelta

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.config import get_config_bool, get_config_int
from utils.logger import emit_structured_event

# ======================================================
# ENVIRONMENT SETUP
# ======================================================
load_dotenv(override=False)
SERPER = os.getenv("SERPER_API_KEY")
GOOGLE_PLACES = os.getenv("GOOGLE_PLACES_API_KEY")
DEFAULT_DISCOVERY_PROVIDER = "google_places" if GOOGLE_PLACES else "serper"
DISCOVERY_PROVIDER = os.getenv("DISCOVERY_PROVIDER", DEFAULT_DISCOVERY_PROVIDER).strip().lower()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_DIR = os.path.expanduser("~/Scripts/Daily_Leads")
DATA_ROOT_DIR = os.path.join(BASE_DIR, "data")
DATA_DIR = os.path.join(DATA_ROOT_DIR, "current")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_DAYS = get_config_int("discovery.cache_ttl_days", default=7, env_var="CACHE_TTL_DAYS")
CACHE_MAX_MB = get_config_int("discovery.cache_max_mb", default=256, env_var="CACHE_MAX_MB")
GOOGLE_DISCOVERY_SEARCH_CALLS = get_config_int("discovery.search_calls", default=2, env_var="GOOGLE_DISCOVERY_SEARCH_CALLS")
GOOGLE_DISCOVERY_TARGET_LEADS = get_config_int("discovery.target_leads", default=12, env_var="GOOGLE_DISCOVERY_TARGET_LEADS")
GOOGLE_DETAILS_FALLBACK_LIMIT = get_config_int("discovery.details_fallback_limit", default=8, env_var="GOOGLE_DETAILS_FALLBACK_LIMIT")
RUN_METRICS_FILE = os.getenv("PIPELINE_RUN_METRICS_FILE", "")
STRUCTURED_LOGGING_ENABLED = get_config_bool(
    "logging.structured.enabled", default=True, env_var="STRUCTURED_LOGGING_ENABLED"
)

RUN_METRICS_TEMPLATE = {
    "google_places": 0,
    "serper": 0,
    "hunter": 0,
    "google_places_calls": 0,
    "google_places_success": 0,
    "google_places_error": 0,
    "google_places_cache_hit": 0,
    "google_places_latency_ms_sum": 0,
    "google_places_latency_ms_count": 0,
    "google_places_text_search_calls": 0,
    "google_places_text_search_success": 0,
    "google_places_text_search_error": 0,
    "google_places_text_search_cache_hit": 0,
    "google_places_text_search_latency_ms_sum": 0,
    "google_places_text_search_latency_ms_count": 0,
    "google_places_details_calls": 0,
    "google_places_details_success": 0,
    "google_places_details_error": 0,
    "google_places_details_cache_hit": 0,
    "google_places_details_latency_ms_sum": 0,
    "google_places_details_latency_ms_count": 0,
    "serper_calls": 0,
    "serper_success": 0,
    "serper_error": 0,
    "serper_cache_hit": 0,
    "serper_latency_ms_sum": 0,
    "serper_latency_ms_count": 0,
    "hunter_calls": 0,
    "hunter_success": 0,
    "hunter_error": 0,
    "hunter_cache_hit": 0,
    "hunter_latency_ms_sum": 0,
    "hunter_latency_ms_count": 0,
}

# ======================================================
# AUTO‑ARCHIVE PREVIOUS DATA FILES
# ======================================================
ARCHIVE_DIR = os.path.join(DATA_ROOT_DIR, "archive")
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
    "yelp.com", "bbb.org", "homeadvisor.com", "angi.com", "thumbtack.com", "manta.com",
    "zoominfo.com", "fandom.com", "wikimedia.org", "elevatorwiki.com", "houzz.com",
    "tiktok.com",
}

NON_BUSINESS_TEXT_HINTS = [
    "[pdf]", "pdf", "jobs", "job", "employment", "salary", "career", "careers",
    "university", "department of", "federal", "government", "wikipedia", "curriculum vitae",
    " seo", "search engine optimization", "digital marketing", "marketing agency",
]


def sanitize_for_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip()).strip("_")


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
        provider = metric_provider_for_cache_prefix(prefix)
        operation = metric_operation_for_cache_prefix(prefix)
        if provider:
            increment_metric(f"{provider}_cache_hit")
            if operation:
                increment_metric(f"{provider}_{operation}_cache_hit")
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


def load_run_metrics():
    data = dict(RUN_METRICS_TEMPLATE)
    if not RUN_METRICS_FILE or not os.path.isfile(RUN_METRICS_FILE):
        return data
    try:
        with open(RUN_METRICS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for key in data:
            data[key] = int(loaded.get(key, 0) or 0)
    except Exception:
        pass
    return data


def save_run_metrics(data):
    if not RUN_METRICS_FILE:
        return
    try:
        with open(RUN_METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def increment_metric(metric_key: str, amount: int = 1):
    if not RUN_METRICS_FILE:
        return
    try:
        data = load_run_metrics()
        if metric_key in data:
            data[metric_key] += int(amount)
            save_run_metrics(data)
    except Exception:
        pass


def increment_api_counter(provider: str):
    """Backward-compatible shim for legacy tests/callers."""
    increment_metric(provider)


def metric_provider_for_cache_prefix(prefix: str) -> str:
    if (prefix or "").startswith("google_place") or prefix == "google_places":
        return "google_places"
    if prefix == "serper":
        return "serper"
    if prefix == "hunter":
        return "hunter"
    return ""


def metric_operation_for_cache_prefix(prefix: str) -> str:
    if prefix == "google_places":
        return "text_search"
    if prefix == "google_place_details":
        return "details"
    return ""


def record_api_outcome(provider: str, success: bool, latency_ms: int, operation: str = ""):
    if provider not in {"google_places", "serper", "hunter"}:
        return
    increment_metric(provider)
    increment_metric(f"{provider}_calls")
    increment_metric(f"{provider}_success" if success else f"{provider}_error")
    increment_metric(f"{provider}_latency_ms_sum", max(0, int(latency_ms)))
    increment_metric(f"{provider}_latency_ms_count")
    if operation:
        increment_metric(f"{provider}_{operation}_calls")
        increment_metric(f"{provider}_{operation}_success" if success else f"{provider}_{operation}_error")
        increment_metric(f"{provider}_{operation}_latency_ms_sum", max(0, int(latency_ms)))
        increment_metric(f"{provider}_{operation}_latency_ms_count")


def run_tracked_api_call(provider: str, request_func, operation: str = ""):
    started = time.perf_counter()
    try:
        result = request_func()
        latency_ms = int((time.perf_counter() - started) * 1000)
        record_api_outcome(provider, success=True, latency_ms=latency_ms, operation=operation)
        return result
    except Exception:
        latency_ms = int((time.perf_counter() - started) * 1000)
        record_api_outcome(provider, success=False, latency_ms=latency_ms, operation=operation)
        raise


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


def prune_cache_size_limit():
    if CACHE_MAX_MB <= 0 or not os.path.isdir(CACHE_DIR):
        return 0

    limit_bytes = CACHE_MAX_MB * 1024 * 1024
    files = []
    total_size = 0

    for name in os.listdir(CACHE_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, name)
        try:
            stat = os.stat(path)
            files.append((path, stat.st_mtime, stat.st_size))
            total_size += stat.st_size
        except Exception:
            continue

    if total_size <= limit_bytes:
        return 0

    files.sort(key=lambda item: item[1])
    removed = 0
    for path, _, file_size in files:
        if total_size <= limit_bytes:
            break
        try:
            os.remove(path)
            removed += 1
            total_size -= file_size
        except Exception:
            continue

    if removed:
        print(f"[CACHE] Pruned {removed} cache file(s) to enforce CACHE_MAX_MB={CACHE_MAX_MB}.")
    return removed


prune_expired_cache()
prune_cache_size_limit()

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
        headers = {"X-API-KEY": SERPER, "Content-Type": "application/json"}
        payload = {"q": query, "num": 10}

        def _request():
            resp = requests.post(
                "https://google.serper.dev/search",
                headers=headers, json=payload, timeout=25
            )
            resp.raise_for_status()
            return resp.json().get("organic", [])

        return run_tracked_api_call("serper", _request)
    
    result = retry_request(_call) or []
    cache_set("serper", query, result)
    return result


def run_google_places_text_search(service: str, town: str):
    """Query Places API (New) Text Search for businesses in a service + city."""
    if not GOOGLE_PLACES:
        print("[WARN] GOOGLE_PLACES_API_KEY missing; cannot use google_places discovery.")
        return []

    key_fingerprint = hashlib.sha256((GOOGLE_PLACES or "").encode("utf-8")).hexdigest()[:12]
    cache_key = f"places_new_v1|{key_fingerprint}|{service}|{town}"
    cached = cache_get("google_places", cache_key)
    if cached is not None:
        return cached

    query = f"{service} in {town}"

    def _call_once(next_page_token: str = ""):
        headers = {
            "X-Goog-Api-Key": GOOGLE_PLACES,
            "X-Goog-FieldMask": (
                "places.id,places.name,places.displayName,places.formattedAddress,"
                "places.googleMapsUri,places.websiteUri,nextPageToken"
            ),
            "Content-Type": "application/json",
        }
        payload = {
            "textQuery": query,
            "pageSize": 20,
        }
        if next_page_token:
            payload["pageToken"] = next_page_token

        def _request():
            resp = requests.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()

        return run_tracked_api_call("google_places", _request, operation="text_search")

    all_results = []
    page_token = ""
    page_count = 0

    page_limit = max(1, GOOGLE_DISCOVERY_SEARCH_CALLS)
    while page_count < page_limit:
        payload = retry_request(_call_once, page_token) or {}
        page_results = payload.get("places", []) or []
        all_results.extend(page_results)
        page_token = payload.get("nextPageToken", "") or ""
        page_count += 1
        if not page_token:
            break
        time.sleep(2)

    cache_set("google_places", cache_key, all_results)
    return all_results


def get_google_place_details(place_id: str):
    """Get website/maps URL details for a specific place resource or ID (Places API New)."""
    if not GOOGLE_PLACES or not place_id:
        return {}

    place_resource = place_id if place_id.startswith("places/") else f"places/{place_id}"
    key_fingerprint = hashlib.sha256((GOOGLE_PLACES or "").encode("utf-8")).hexdigest()[:12]
    cache_key = f"places_new_v1_details|{key_fingerprint}|{place_resource}"
    cached = cache_get("google_place_details", cache_key)
    if cached is not None:
        return cached

    def _call():
        headers = {
            "X-Goog-Api-Key": GOOGLE_PLACES,
            "X-Goog-FieldMask": "id,name,displayName,formattedAddress,googleMapsUri,websiteUri",
        }

        def _request():
            resp = requests.get(
                f"https://places.googleapis.com/v1/{place_resource}",
                headers=headers,
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()

        return run_tracked_api_call("google_places", _request, operation="details")

    details = retry_request(_call) or {}
    cache_set("google_place_details", cache_key, details)
    return details


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

    # Strong heuristic: if result points to a non-directory domain, assume website exists.
    # This avoids missing valid business sites when HTTP probing is blocked or unreliable.
    if "." in domain:
        return True

    # If the business name appears in the domain, likely a real business site
    clean_name = re.sub(r"[^a-z0-9]", "", business_name.lower())
    clean_domain = re.sub(r"[^a-z0-9]", "", domain.replace("www.", "").split(".")[0])
    if clean_name and clean_name in clean_domain:
        return True

    # Quick probe — is this an actual functional site?
    for candidate in (f"https://{domain}", f"http://{domain}"):
        try:
            resp = requests.get(candidate, headers=HEADERS, timeout=6, allow_redirects=True)
            if 200 <= resp.status_code < 400:
                content_type = (resp.headers.get("Content-Type", "") or "").lower()
                body = (resp.text or "")[:3000]
                if "html" in content_type or re.search(r"<html|<!doctype", body, re.I):
                    return True
        except Exception:
            continue

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
        emit_structured_event(
            "discovery_start",
            enabled=STRUCTURED_LOGGING_ENABLED,
            service=service,
            city=town,
            provider=DISCOVERY_PROVIDER,
        )
        print(f"[DISCOVERY] {service.title()} | {town.title()} – Scanning...")

        # Safe filenames
        safe_city = sanitize_for_filename(town)
        safe_service = sanitize_for_filename(service)
        today = date.today().strftime("%Y-%m-%d")

        out_path = os.path.join(
            DATA_DIR,
            f"leads_{safe_city}_{safe_service}_NO_WEBSITE_{today}.csv"
        )

        provider = DISCOVERY_PROVIDER
        serper_query = (
            f'"{service}" "{town}" ("no website" OR "no site" OR "site coming soon" '
            f'OR "under construction" OR "Google My Business" OR "business.site") '
            f'-site:facebook.com -site:yelp.com -site:linkedin.com '
            f'-site:bbb.org -site:angi.com -site:thumbtack.com'
        )
        if provider == "google_places" and not GOOGLE_PLACES:
            print("[WARN] DISCOVERY_PROVIDER=google_places but key missing; falling back to serper.")
            provider = "serper"

        if provider == "google_places":
            results = run_google_places_text_search(service, town)
            if not results and SERPER:
                print("[FALLBACK] Google Places returned no results; trying Serper discovery.")
                provider = "serper"
                results = run_serper_search(serper_query)
        else:
            results = run_serper_search(serper_query)

        if not results:
            print(f"[WARN] No discovery results for {town} | {service}")
            emit_structured_event(
                "discovery_no_results",
                enabled=STRUCTURED_LOGGING_ENABLED,
                service=service,
                city=town,
                provider=provider,
            )
            return None

        leads = []
        details_fallback_count = 0
        target_leads = max(1, GOOGLE_DISCOVERY_TARGET_LEADS)
        details_fallback_limit = max(0, GOOGLE_DETAILS_FALLBACK_LIMIT)

        for item in results:
            if provider == "google_places":
                display_name = item.get("displayName") or {}
                title = (display_name.get("text") or item.get("name") or "").strip()
                place_id = (item.get("name") or item.get("id") or "").strip()
                details = {}
                website = (item.get("websiteUri") or "").strip()
                maps_link = (item.get("googleMapsUri") or "").strip()
                snippet = (item.get("formattedAddress") or "").strip()

                should_fetch_details = (
                    not website and place_id and details_fallback_count < details_fallback_limit
                )
                if should_fetch_details:
                    details = get_google_place_details(place_id)
                    details_fallback_count += 1

                website = (website or details.get("websiteUri") or "").strip()
                maps_link = (
                    maps_link
                    or details.get("googleMapsUri")
                    or ""
                ).strip()
                snippet = (
                    snippet
                    or details.get("formattedAddress")
                    or ""
                ).strip()
                link = maps_link
                if website:
                    if DEBUG:
                        print(f"[SKIP] Google Places details has website for {title}: {website}")
                    continue
            else:
                title = item.get("title", "").strip()
                link = item.get("link", "")
                snippet = item.get("snippet", "")

            if not title or not link:
                continue

            if should_skip_non_business_result(title, link, snippet):
                if DEBUG:
                    print(f"[SKIP-NONBIZ] {title} -> {link}")
                continue

            if provider != "google_places":
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

            if provider == "google_places" and len(leads) >= target_leads:
                if DEBUG:
                    print(f"[STOP] Reached target leads ({target_leads}) for {service} | {town}")
                break

            time.sleep(0.5)

        if not leads:
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                    print(f"[CLEANUP] Removed stale discovery file: {out_path}")
                except Exception as cleanup_err:
                    print(f"[WARN] Could not remove stale discovery file: {cleanup_err}")
            print(f"[WARN] All potential results had websites for {town} | {service}")
            emit_structured_event(
                "discovery_no_leads_after_filter",
                enabled=STRUCTURED_LOGGING_ENABLED,
                service=service,
                city=town,
                provider=provider,
            )
            return None

        # Write safely‑named CSV
        df = pd.DataFrame(leads).drop_duplicates(subset=["name"])
        df.to_csv(out_path, index=False)
        valid_emails = df['email'].notna().sum() if 'email' in df.columns else 0
        print(f"[STATS] Leads discovered: {len(df)} | Emails found: {valid_emails}")
        print(f"[OK] Discovery complete – {len(df)} leads saved → {out_path}")
        emit_structured_event(
            "discovery_complete",
            enabled=STRUCTURED_LOGGING_ENABLED,
            service=service,
            city=town,
            provider=provider,
            leads_discovered=int(len(df)),
            output_file=out_path,
        )
        return out_path

    except Exception as e:
        print(f"[ERROR] Discovery error for {service} | {town}: {e}")
        emit_structured_event(
            "discovery_error",
            enabled=STRUCTURED_LOGGING_ENABLED,
            service=service,
            city=town,
            error=str(e),
        )
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
        archive_old_data()
        discover(sys.argv[1], sys.argv[2])