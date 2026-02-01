#!/bin/zsh

# --- Load environment variables from .env ---
set -o allexport
source "$(dirname $0)/../.env"
set +o allexport

# --- Move to project root ---
cd "$(dirname "$0")/.."

# --- Optional: sanity check ---
echo "Loaded GOOGLE_PLACES_API_KEY prefix: ${GOOGLE_PLACES_API_KEY:0:8}"

# --- Run Python script ---
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  /Users/alexcahn/Scripts/Daily_Leads/src/lead_generator_no_website_enriched.py \
  >> /Users/alexcahn/Scripts/Daily_Leads/logs/daily_run.log \
  2>> /Users/alexcahn/Scripts/Daily_Leads/logs/daily_run_error.log
