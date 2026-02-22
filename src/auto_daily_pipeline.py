#!/usr/bin/env python3
"""
auto_daily_pipeline.py
-------------------------------------------------
Runs complete daily workflow for multiple services & cities.
1. Generate leads via Google Places (once per town/service)
2. Filter to no‑website businesses
3. Find emails (Serper + Hunter)
4. Email final CSV reports
-------------------------------------------------
"""

import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DATESTAMP = datetime.now().strftime("%Y‑%m‑%d")

# --------------------------------------------------
# Define your daily targets here
# --------------------------------------------------
SERVICES = ["plumber", "roofer", "electrician", "hvac", "cleaning service"]
CITIES = ["Seattle", "Portland", "Boise", "Denver", "Sacramento"]

# --------------------------------------------------
def run_cmd(description, cmd):
    """Run a subprocess command safely."""
    print(f"\n[▶] {description}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[⚠] Step failed: {description}\n")
    else:
        print(f"[✅] Done: {description}")

# --------------------------------------------------
def main():
    for service in SERVICES:
        for city in CITIES:
            print(f"\n{'='*70}\n[RUNNING] {service.title()} in {city} ({DATESTAMP})\n{'='*70}")
            # 1. Generate today's leads
            run_cmd("Google Places Data Pull",
                f"python3 {os.path.join(BASE_DIR,'lead_generator_email.py')} '{service}' '{city}'")
            # 2. Filter for no‑website
            run_cmd("Filter for No‑Website Leads",
                f"python3 {os.path.join(BASE_DIR,'filter_no_website.py')} '{service}' '{city}'")
            # 3. Email lookup for no‑website leads
            run_cmd("Find No‑Website Emails",
                f"python3 {os.path.join(BASE_DIR,'find_no_website_emails.py')} '{service}' '{city}'")

    # 4. After all jobs, send consolidated reports
    run_cmd("Send Daily Email Summary",
        f"python3 {os.path.join(BASE_DIR,'daily_report_emailer.py')}")

# --------------------------------------------------
if __name__ == "__main__":
    main()