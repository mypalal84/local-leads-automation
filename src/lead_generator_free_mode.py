#!/usr/bin/env python3
# ------------------------------------------------------------
# Lead Generator (Free Mode, March 2025+ Caps)
# Enforces Places API 5,000-call monthly limit automatically.
# ------------------------------------------------------------
import os, re, json, time, requests, pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
CACHE_DIR = os.path.join(BASE_DIR, "..", "cache")
OUTPUT_DIR = BASE_DIR
USAGE_LOG = os.path.join(CACHE_DIR, "usage_log.json")
HISTORY_FILE = os.path.join(DATA_DIR, "lead_history.csv")
TOWNS_FILE = os.path.join(DATA_DIR, "towns_1000.csv")
os.makedirs(CACHE_DIR, exist_ok=True)
MAX_CALLS = 5000  # new free monthly limit
MAX_LEADS_PER_DAY = 50

GOOGLE_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not GOOGLE_KEY:
    raise RuntimeError("Missing GOOGLE_PLACES_API_KEY")

# --- Usage Counter ---
def reset_monthly_usage():
    now = datetime.utcnow()
    if os.path.exists(USAGE_LOG):
        dat = json.load(open(USAGE_LOG))
        last = datetime.fromisoformat(dat.get("month","1970-01-01"))
        if last.year != now.year or last.month != now.month:
            dat = {"count":0, "month": now.strftime("%Y-%m-%d")}
            with open(USAGE_LOG, "w") as f:
                json.dump(dat, f)
    else:
        dat = {"count":0, "month": now.strftime("%Y-%m-%d")}
        json.dump(dat, open(USAGE_LOG, "w"))
    return dat

def track_usage():
    dat = json.load(open(USAGE_LOG)) if os.path.exists(USAGE_LOG) else reset_monthly_usage()
    dat["count"] += 1
    dat["month"] = datetime.utcnow().strftime("%Y-%m-%d")
    json.dump(dat, open(USAGE_LOG, "w"))
    return dat["count"]

# --- Places with Caching + Cap Enforcement ---
def cached_places_search(query):
    fn = os.path.join(CACHE_DIR, f"places_{re.sub(r'[^a-zA-Z0-9_]', '_', query)}.json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 7 * 86400:
        return json.load(open(fn))
    dat = json.load(open(USAGE_LOG)) if os.path.exists(USAGE_LOG) else reset_monthly_usage()
    if dat["count"] >= MAX_CALLS:
        print("🟡  Reached monthly free tier limit. Using cache only.")
        return []
    try:
        count = track_usage()
        if count > MAX_CALLS:
            print("🛑 Free tier cap reached; stopping API calls.")
            return []
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query.replace(' ', '+')}&key={GOOGLE_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json().get("results", [])
        with open(fn, "w") as f: json.dump(data, f)
        print(f"✅ [{count}/{MAX_CALLS}] Query success → {query}")
        return data
    except Exception as e:
        print(f"⚠️ Places API error: {e}")
        return []

# --- Free Email Search and Pattern Generator ---
def free_email_search(name, town):
    fn = os.path.join(CACHE_DIR, f"email_{re.sub(r'[^a-zA-Z0-9_]', '_', name+town)}.json")
    if os.path.exists(fn):
        return json.load(open(fn)).get("email",""), "Cache"
    q = f"{name} {town} contact email"
    try:
        resp = requests.get("https://duckduckgo.com/html/", params={"q": q}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = ' '.join(a.get_text() for a in soup.select('a.result__snippet'))
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        email = emails[0] if emails else ""
        src = "DuckDuckGo" if email else "Pattern"
    except Exception as e:
        email, src = "", f"Error:{e}"
    json.dump({"email": email, "src": src}, open(fn,"w"))
    return email, src

def pattern_generator(name, town):
    domain = f"{re.sub(r'[^a-zA-Z0-9]', '', town.lower())}.com"
    base = re.sub(r'[^a-z]', '', name.split()[0].lower())
    patterns = [f"info@{domain}", f"contact@{domain}", f"{base}@{domain}"]
    return ', '.join(patterns), "Pattern"

def normalize_place(p, service):
    return {
        "name": p.get("name", ""),
        "address": p.get("formatted_address") or p.get("vicinity",""),
        "rating": p.get("rating"),
        "place_id": p.get("place_id"),
        "service": service
    }

# --- Main Routine ---
def main():
    reset_monthly_usage()
    df = pd.read_csv(TOWNS_FILE)
    sample_towns = df.sample(5)
    SERVICES = ["plumber","roofer","electrician","hvac","cleaning service"]
    leads = []

    for _, r in sample_towns.iterrows():
        for svc in SERVICES:
            q = f"{svc} {r['Town']}, {r['State']}"
            results = cached_places_search(q)
            for place in results:
                p = normalize_place(place, svc)
                name = p["name"]; address = p["address"]
                town = address.split(",")[0] if address else r["Town"]
                email, src = free_email_search(name, town)
                if not email:
                    email, src = pattern_generator(name, town)
                leads.append({
                    "Business": name,
                    "Town": town,
                    "Service": svc,
                    "Email": email,
                    "Source": src,
                    "Rating": p["rating"],
                    "Date": datetime.now().strftime("%Y-%m-%d")
                })

    if not leads:
        print("No new leads found or quota exhausted.")
        return

    out = pd.DataFrame(leads).head(MAX_LEADS_PER_DAY)
    fpath = os.path.join(OUTPUT_DIR, f"no_website_free_{datetime.now():%Y-%m-%d}.csv")
    out.to_csv(fpath, index=False)
    print(f"✅ Saved {len(out)} leads → {fpath}")
    usage = json.load(open(USAGE_LOG))
    print(f"🌐 API usage this month: {usage['count']}/{MAX_CALLS}")

if __name__ == "__main__":
    main()
