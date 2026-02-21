#!/usr/bin/env python3
# ===========================================================
#  Lead Generator Email – Randomized, Expanded, Weighted (Feb 2026)
# ===========================================================
import os
import csv
import re
import random
import smtplib
import requests
import pandas as pd
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from urllib.parse import urlparse
from dotenv import load_dotenv

# -----------------------------------------------------------
#  Load environment variables
# -----------------------------------------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HUNTER_KEY = os.getenv("HUNTER_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# -----------------------------------------------------------
#  Randomized constants
# -----------------------------------------------------------
ALL_SERVICES = [
    "plumber", "roofer", "electrician", "hvac", "landscaper",
    "contractor", "cleaning service", "handyman", "painter",
    "tree service", "pest control", "garage door repair",
    "fence installer", "gutter cleaning", "flooring installer",
    "window cleaning", "solar installer", "junk removal",
    "pressure washing", "pool cleaning", "appliance repair",
    "masonry", "remodeling contractor",
]
SERVICES = random.sample(ALL_SERVICES, k=random.randint(5, 8))

MAX_LEADS = 50
HUNTER_MAX_QUOTA = 50  # Free tier limit

# -----------------------------------------------------------
#  Load towns with weighting
# -----------------------------------------------------------
TOWNS_PATH = os.path.join(os.path.dirname(__file__), "../data/towns_1000.csv")
TOWNS = []
if os.path.exists(TOWNS_PATH):
    try:
        towns_df = pd.read_csv(TOWNS_PATH)
        if {"Town", "State", "Population"}.issubset(towns_df.columns):
            towns_df = towns_df.dropna(subset=["Town", "State", "Population"])
            n = random.randint(8, 12)
            n = min(n, len(towns_df))
            TOWNS = (
                towns_df.sample(
                    n=n,
                    weights = towns_df["Population"] ** 0.5,
                    random_state=None,
                )[["Town", "State"]]
                .to_dict("records")
            )
            print(f"📊 Loaded {len(towns_df)} towns — sampled {n} weighted by Population.")
        else:
            print("⚠️ towns_1000.csv missing required columns, using fallback set.")
    except Exception as e:
        print(f"⚠️ Failed to load towns_1000.csv: {e}")
else:
    print("⚠️ No towns_1000.csv found — using static fallback towns.")

if not TOWNS:
    TOWNS = [
        {"Town": "La Mirada", "State": "CA"},
        {"Town": "Lincoln", "State": "NE"},
        {"Town": "Florissant", "State": "MO"},
        {"Town": "Nashville", "State": "TN"},
        {"Town": "Tempe", "State": "AZ"},
        {"Town": "Kirkland", "State": "WA"},
        {"Town": "Orlando", "State": "FL"},
        {"Town": "Waco", "State": "TX"},
        {"Town": "Reno", "State": "NV"},
        {"Town": "Boise", "State": "ID"},
    ]

random.shuffle(TOWNS)

# -----------------------------------------------------------
#  Utilities
# -----------------------------------------------------------
def google_places_search(query):
    """Return list of places for given text query via Places API v1"""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,"
            "places.websiteUri,places.internationalPhoneNumber"
        ),
    }
    payload = {"textQuery": query}
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 200:
        print(f"⚠️ Google Places error {r.status_code}: {r.text[:100]}")
        return []
    return r.json().get("places", [])


def hunter_email_lookup(domain, company):
    if not domain:
        return "", "Pattern"
    try:
        params = {"domain": domain, "api_key": HUNTER_KEY, "company": company}
        r = requests.get("https://api.hunter.io/v2/domain-search", params=params, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Hunter status {r.status_code} for {domain}")
            return "", "Pattern"
        emails = r.json().get("data", {}).get("emails", [])
        if emails:
            return emails[0].get("value", ""), "Hunter.io"
        return "", "Pattern"
    except Exception as e:
        print(f"⚠️ Hunter error: {e}")
        return "", "Pattern"


def fallback_email(name, town):
    prefixes = ["info", "office", "contact", "team", (name.split()[0] if name else "info").lower()]
    prefix = random.choice(prefixes)
    domain = re.sub(r"[^a-z]", "", town.lower()) + ".com"
    return f"{prefix}@{domain}", "Pattern"


def send_summary_email(csv_path, subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(csv_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(csv_path))
    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(csv_path)}"'
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)
    print(f"✅ Summary email sent to {EMAIL_USER}")


# -----------------------------------------------------------
#  Main pipeline
# -----------------------------------------------------------
def main():
    print("🧭 Today's selection:")
    print(f"Services: {SERVICES}")
    print(pd.DataFrame(TOWNS)[["Town", "State"]])

    daily_leads, total_places, hunter_calls, hunter_hits, fallback_hits = [], 0, 0, 0, 0

    for t in TOWNS:
        for svc in SERVICES:
            query = f"{svc} {t['Town']}"
            results = google_places_search(query)
            total_places += len(results)
            print(f"🔍 {len(results)} results for '{svc} {t['Town']}'")
            for r in results:
                name = r.get("displayName", {}).get("text", "").strip()
                addr = r.get("formattedAddress", "").strip()
                phone = r.get("internationalPhoneNumber", "").strip()
                site = r.get("websiteUri", "").strip()
                if not name:
                    continue

                email, src = "", "Pattern"
                if site and hunter_calls < HUNTER_MAX_QUOTA:
                    domain = urlparse(site).netloc.replace("www.", "")
                    email, src = hunter_email_lookup(domain, name)
                    hunter_calls += 1
                    if src == "Hunter.io" and email:
                        hunter_hits += 1
                if not email:
                    email, src = fallback_email(name, t["Town"])
                    fallback_hits += 1

                daily_leads.append(
                    {
                        "Business": name,
                        "Town": t["Town"],
                        "Service": svc,
                        "Email": email,
                        "Source": src,
                        "Address": addr,
                        "Phone": phone,
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                    }
                )
                if len(daily_leads) >= MAX_LEADS:
                    break
            if len(daily_leads) >= MAX_LEADS:
                break
        if len(daily_leads) >= MAX_LEADS:
            break

    df = (
        pd.DataFrame(daily_leads)
        .drop_duplicates(subset=["Business", "Town", "Service"])
        .sort_values(by=["Town", "Service"])
    )
    out_path = os.path.join(
        os.path.dirname(__file__),
        f"daily_enriched_leads_{datetime.now():%Y-%m-%d}.csv",
    )
    df.to_csv(out_path, index=False)
    print(f"✅ {len(df)} enriched leads saved to {out_path}")

    summary = (
        f"Google Places queried: {total_places}\n"
        f"Hunter calls made: {hunter_calls}\n"
        f"Hunter emails found: {hunter_hits}\n"
        f"Fallback emails used: {fallback_hits}\n"
        f"Total leads saved: {len(df)}"
    )
    print(summary)
    send_summary_email(out_path, f"Daily Leads {datetime.now():%Y-%m-%d}", summary)
    print("🎯 Pipeline complete.")


if __name__ == "__main__":
    main()