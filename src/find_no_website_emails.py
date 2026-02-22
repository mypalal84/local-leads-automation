#!/usr/bin/env python3
"""
find_no_website_emails.py
------------------------------------------------------
Find verified business contact emails for "no website" leads.

✅ v2026.2.22 — Production Optimized
Includes:
 - Deduplicate domains (keeps first occurrence)
 - Optional Hunter confidence recording
 - Debug mode controlled via DEBUG=true in .env
 - Safe cron scheduling with minimal console noise
 - Expanded filters for irrelevant corporate/government sites
------------------------------------------------------
"""

import os, re, time, requests, pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# --------------------------------------------------
# Environment setup
# --------------------------------------------------
load_dotenv()
SERPER = os.getenv("SERPER_API_KEY")
HUNTER = os.getenv("HUNTER_API_KEY")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DATESTAMP = datetime.now().strftime("%Y-%m-%d")

# --------------------------------------------------
# Search via Serper
# --------------------------------------------------
def search_serper(query):
    """Queries Serper for likely business domains."""
    try:
        payload = {"q": query, "num": 10}
        headers = {"X-API-KEY": SERPER, "Content-Type": "application/json"}
        r = requests.post("https://google.serper.dev/search",
                          headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        results = r.json().get("organic", [])
        links = [o.get("link") for o in results if o.get("link")]
        block = [
            "facebook.com", "instagram.com", "yelp.com", "linkedin.com",
            "bbb.org", "angieslist.com", "homeadvisor.com",
            "mapquest.com", "yellowpages.com"
        ]
        clean_links = [l for l in links if not any(b in l for b in block)]
        if DEBUG:
            print(f"[DEBUG] Serper returned {len(clean_links)} URLs for query → {query}")
        return clean_links
    except Exception as e:
        print("[ERR] Serper search error:", e)
        return []

# --------------------------------------------------
# Hunter email lookup
# --------------------------------------------------
def hunter_email_lookup(domain):
    """Fetch verified emails from Hunter.io."""
    try:
        clean_domain = domain.replace("www.", "").split("/")[0]
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": clean_domain, "api_key": HUNTER},
            timeout=20
        )
        if resp.status_code != 200:
            print(f"[ERR] Hunter HTTP {resp.status_code} for {clean_domain}")
            return []
        data = resp.json().get("data", {})
        email_objs = data.get("emails", [])
        if not email_objs:
            return []

        results = []
        for e in email_objs:
            address = e.get("value")
            conf = e.get("confidence")
            if address:
                results.append(f"{address}|{conf}" if conf is not None else address)

        if DEBUG:
            preview = [x.split("|")[0] for x in results[:3]]
            print(f"[DEBUG] Hunter found {len(results)} emails for {clean_domain}: {preview}")
        return sorted(set(results))
    except Exception as e:
        print("[ERR] Hunter lookup:", e)
        return []

# --------------------------------------------------
# Email enrichment per lead
# --------------------------------------------------
def enrich(service, town):
    """Main enrichment routine."""
    fname = f"leads_{town}_{service}_NO_WEBSITE_{DATESTAMP}.csv"
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        print(f"[ERR] Missing lead file: {path}")
        return

    df = pd.read_csv(path)
    results, found, none = [], 0, 0

    # Irrelevant / corporate / gov domains to skip
    irrelevant = [
        "reddit.com", "bryant.com", "seattle.gov", "breakthroughenergy.org",
        "jobs.johnsoncontrols.com", "secure.lni.wa.gov"
    ]

    print(f"[INFO] Starting enrichment: {len(df)} leads for {town.title()} - {service.title()}.\n")

    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip() or "unknown"
        query = f"{name} {town} {service} site OR contact OR email"

        print(f"[INFO] Searching {name} ...")
        links = search_serper(query)
        if DEBUG:
            print(f"[DEBUG] Links ({len(links)}): {links}")

        emails_accumulated = set()
        row["website"], row["emails"], row["confidence_score"] = "", "", "none"

        for link in links:
            match = re.search(r"https?://([^/]+)/?", link)
            if not match:
                continue
            domain = match.group(1).lower()
            if any(bad in domain for bad in irrelevant):
                print(f"[SKIP] {domain} — flagged as irrelevant.")
                continue

            emails = hunter_email_lookup(domain)
            if not emails:
                continue

            for e in emails:
                emails_accumulated.add(e)
            row["website"] = f"https://{domain}"
            row["confidence_score"] = "direct"
            if DEBUG:
                print(f"[FOUND] {domain} → {emails[:3]}")

        if emails_accumulated:
            found += 1
            row["emails"] = ", ".join(sorted(emails_accumulated))
        else:
            none += 1

        results.append(row)
        time.sleep(1)  # rate-limit for API

    # Create dataframe result
    df_out = pd.DataFrame(results)
    df_out["root_domain"] = df_out["website"].str.extract(r"https?://([^/]+)/?")
    deduped = df_out.drop_duplicates(subset=["root_domain"]).drop(columns=["root_domain"], errors="ignore")

    out_path = os.path.join(DATA_DIR, f"no_website_emails_{town}_{service}_{DATESTAMP}.csv")
    deduped.to_csv(out_path, index=False)

    total = found + none
    print("\n--------------------------------------------------")
    print(f"[📧] Hunter Results for {service.title()} in {town.title()}")
    print(f"  • Leads processed : {total}")
    print(f"  • Leads w/ emails : {found}")
    print(f"  • No matches      : {none}")
    print(f"  • Unique domains  : {deduped['website'].nunique()}")
    print(f"  • Output file     : {out_path}")
    print("--------------------------------------------------\n")
    return out_path

# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 find_no_website_emails.py <service> <city>")
    else:
        enrich(sys.argv[1], sys.argv[2])