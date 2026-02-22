#!/usr/bin/env python3
import os, sys, json, time, csv, requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATESTAMP = datetime.now().strftime("%Y-%m-%d")

def get_places_for_query(query, max_results=50):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.websiteUri,places.rating"
    }
    payload = {"textQuery": query, "pageSize": min(max_results, 20)}
    all_places, token = [], None
    while True:
        if token: payload["pageToken"] = token
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        data = r.json()
        for p in data.get("places", []):
            all_places.append({
                "name": p.get("displayName", {}).get("text"),
                "address": p.get("formattedAddress"),
                "website": p.get("websiteUri") or "",
                "rating": p.get("rating", ""),
                "emails": "",
                "source": "Google"
            })
        token = data.get("nextPageToken")
        if not token or len(all_places) >= max_results: break
        time.sleep(2)
    return all_places

def save_to_csv(rows, service, town):
    path = os.path.join(DATA_DIR, f"leads_{town}_{service}_{DATESTAMP}.csv")
    keys = ["name","address","website","emails","rating","source"]
    with open(path,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)
    return path

if __name__=="__main__":
    if len(sys.argv)<3: print("Usage: python3 lead_generator_email.py <service> <city>"); sys.exit(1)
    service, town = sys.argv[1], sys.argv[2]
    query=f"{service} {town}"
    print(f"[INFO] Fetching {query}")
    leads=get_places_for_query(query)
    out=save_to_csv(leads, service, town)
    print(f"[✅] Saved {len(leads)} leads → {out}")