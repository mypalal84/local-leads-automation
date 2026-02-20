#!/usr/bin/env python3
import os
import pandas as pd
import random
import requests
import smtplib
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOWNS_FILE = os.path.join(BASE_DIR, "..", "data", "towns_1000.csv")
OUTPUT_DIR = BASE_DIR
HISTORY_FILE = os.path.join(BASE_DIR, "..", "data", "lead_history.csv")
MAX_LEADS_PER_DAY = 50

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

EMAIL_SENDER = os.getenv("DAILY_LEAD_EMAIL_SENDER")
EMAIL_PASS = os.getenv("DAILY_LEAD_EMAIL_PASS")
EMAIL_TO = os.getenv("DAILY_LEAD_EMAIL_TO")
SMTP_SERVER, SMTP_PORT = "smtp.gmail.com", 587

SERVICES = [
    "plumber","roofer","electrician","contractor","landscaper","hvac",
    "dog walker","dentist","chiropractor","pest control","cleaning service",
    "auto repair","towing service","car wash","appliance repair","handyman",
    "hair salon","barber","personal trainer","fitness coach","pet grooming",
    "moving company","storage facility","lawyer","accountant","locksmith"
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

key = GOOGLE_PLACES_API_KEY
if not key:
    raise RuntimeError("❌ GOOGLE_PLACES_API_KEY not found in environment.")

# Ensure lead_history.csv exists
if not os.path.exists(HISTORY_FILE):
    print("⚙️  No existing lead_history.csv found — creating a new one.")
    history = pd.DataFrame(columns=[
        "Business","Phone","Email (Enriched)","Town","Service","DateFound"
    ])
    history.to_csv(HISTORY_FILE, index=False)
else:
    print("📄 Loading existing lead_history.csv")
    history = pd.read_csv(HISTORY_FILE)

# ================= HELPER FUNCTIONS =================
def safe_get(url, **kwargs):
    try:
        return requests.get(url, **kwargs)
    except Exception:
        return None

def run_places_search(query):
    key = os.getenv("GOOGLE_PLACES_API_KEY")
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query.replace(' ', '+')},USA&key={key}"
    r = requests.get(url)
    data = r.json()
    if data.get("status") != "OK":
        print(f"⚠️ Google Places search failed for query: {query} → {data.get('status')}")
        return []
    return data["results"]

def get_place_details(pid):
    u = "https://maps.googleapis.com/maps/api/place/details/json"
    r = safe_get(u, params={
        "place_id": pid,
        "fields": "name,website,formatted_phone_number",
        "key": GOOGLE_PLACES_API_KEY
    }, timeout=10)
    res = r.json().get("result", {}) if r else {}
    return res.get("website", ""), res.get("formatted_phone_number", "")

def is_social(u: str):
    if not u:
        return False
    return any(s in u.lower() for s in ["facebook","instagram","linkedin","twitter","tiktok"])

# Normalize Google Places result for consistent keys
def normalize_place(p, service=None):
    return {
        "business": p.get("name", ""),
        "address": p.get("formatted_address") or p.get("vicinity") or "",
        "website": p.get("website") or "",
        "phone": p.get("formatted_phone_number") or "",
        "rating": p.get("rating"),
        "place_id": p.get("place_id", ""),
        "service": service or "",
    }

# ============== ENRICHMENT (unchanged core) ================
def enrich_email(name, town):
    import json
    pattern=r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}"

    # —— Try Serper
    if SERPER_API_KEY:
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type":"application/json"}
        for q in [f"{name} {town} email", f"{name} {town} contact"]:
            try:
                r=requests.post("https://google.serper.dev/search",headers=headers,json={"q":q,"num":5},timeout=10)
                if r.status_code==403:
                    print(f"🚫 Serper 403 for {name} — switching to SerpApi."); break
                data=r.json()
                found=[]
                for i in data.get("organic",[]): 
                    snippet=i.get("snippet","")+i.get("title","")
                    found+=re.findall(pattern,snippet)
                if found: 
                    print(f"🔁 Serper success for {name}")
                    return ", ".join(dict.fromkeys(found)),"Serper"
            except Exception as e:
                print(f"⚠️ Serper error for {name}: {e}"); break

    # —— Try SerpApi
    if SERPAPI_API_KEY:
        for q in [f"{name} {town} email", f"{name} {town} contact"]:
            try:
                params={"api_key":SERPAPI_API_KEY,"engine":"google","q":q,"num":5}
                r=requests.get("https://serpapi.com/search.json",params=params,timeout=10)
                data=r.json(); found=[]
                for i in data.get("organic_results",[]):
                    snippet=i.get("snippet","")+i.get("title","")
                    found+=re.findall(pattern,snippet)
                if found:
                    print(f"🔁 SerpApi success for {name}")
                    return ", ".join(dict.fromkeys(found)),"SerpApi"
            except Exception as e:
                print(f"⚠️ SerpApi error for {name}: {e}"); break

    # —— Try Hunter
    if HUNTER_API_KEY:
        try:
            r = requests.get(
                "https://api.hunter.io/v2/domain-search",
                params={"company": name,"api_key": HUNTER_API_KEY,"limit": 1},
                timeout=10
            )
            data = r.json().get("data", {})
            email = None
            if "emails" in data and data["emails"]:
                email = data["emails"][0].get("value")
            if email:
                print(f"✅ Hunter.io found: {email}")
                return email, "Hunter.io"
            else:
                print(f"ℹ️ Hunter.io found no email for {name} (status {r.status_code})")
        except Exception as e:
            print(f"⚠️ Hunter error: {e}")

    # —— Pattern fallback
    domain=re.sub(r"[^a-zA-Z0-9.-]","",town.split()[0].lower())+".com"
    base=name.split()[0].lower().replace("&","").replace(".","")
    patterns=[f"info@{domain}",f"contact@{domain}",f"{base}@{domain}"]
    return ", ".join(patterns), "Pattern Generator"

# ============== EMAIL & HISTORY ============
def send_email(body, attachment=None):
    try:
        if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_TO]): 
            return print("⚠️ Email credentials missing.")
        msg=MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = EMAIL_SENDER, EMAIL_TO, "Daily Leads"
        msg.attach(MIMEText(body, "plain"))
        if attachment and os.path.exists(attachment):
            part = MIMEBase("application","octet-stream")
            part.set_payload(open(attachment,"rb").read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment)}")
            msg.attach(part)
        s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        s.starttls()
        s.login(EMAIL_SENDER, EMAIL_PASS)
        s.send_message(msg)
        s.quit()
        print(f"📧 Email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"⚠️ Email failure: {e}")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            return pd.read_csv(HISTORY_FILE)
        except Exception:
            print("⚠️ History read error.")
    return pd.DataFrame()

def update_history(df):
    old = load_history()
    all_df = pd.concat([old, df]).drop_duplicates(subset=["Business","Phone","Email (Enriched)"])
    all_df.to_csv(HISTORY_FILE, index=False)

# ================= MAIN ===================
def main():
    if not os.path.exists(TOWNS_FILE):
        raise FileNotFoundError(f"CSV not found at: {TOWNS_FILE}")
    df = pd.read_csv(TOWNS_FILE)
    sampled_towns = df.sample(10)

    queries = [f"{svc} {r['Town']}, {r['State']}" for _, r in sampled_towns.iterrows() for svc in SERVICES]
    leads, hist = [], load_history()

    for query in queries:
        service = query.split()[0]
        results = run_places_search(query)
        for raw in results:
            p = normalize_place(raw, service)
            site, phone = get_place_details(p["place_id"])
            if site and not is_social(site):
                continue

            address = p.get("address")
            town = address.split(",")[0] if address else ""

            # Skip if already in history
            if not hist.empty and not hist[hist["Business"]==p["business"]].empty:
                continue

            email, src = enrich_email(p["business"], town)
            leads.append({
                "Business": p["business"],
                "Phone": phone or "",
                "Presence": "No website",
                "Email (Enriched)": email,
                "Search Provider Used": src,
                "Town": town,
                "Service": p["service"],
                "Rating": p["rating"],
                "GoogleMaps Link": f"https://www.google.com/maps/place/?q=place_id:{p['place_id']}"
            })

    if not leads:
        print("No new leads found.")
        return

    out = pd.DataFrame(leads).head(MAX_LEADS_PER_DAY)
    out["Rating"] = pd.to_numeric(out["Rating"], errors="coerce")
    out = out.sort_values("Rating", ascending=False, na_position="last")
    name = os.path.join(OUTPUT_DIR, f"no_website_v5_{datetime.now():%Y-%m-%d}.csv")

    out.to_csv(name, index=False)
    update_history(out)
    msg = f"✅ {datetime.now():%Y-%m-%d}: {len(out)} leads fetched (Serper → SerpApi → Hunter → Pattern)."
    print(msg)
    send_email(msg, name)

if __name__ == "__main__":
    main()