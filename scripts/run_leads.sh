#!/bin/zsh

export SERPER_API_KEY="your_real_serper_key"
export SERPAPI_API_KEY="your_real_serpapi_key"
export HUNTER_API_KEY="your_real_hunter_key"
export GOOGLE_PLACES_API_KEY="your_real_google_places_key"
export DAILY_LEAD_EMAIL_SENDER="your_gmail@gmail.com"
export DAILY_LEAD_EMAIL_PASS="your_app_password"
export DAILY_LEAD_EMAIL_TO="your_gmail@gmail.com"

/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  /Users/alexcahn/Scripts/Daily_Leads/scr/lead_generator_no_website_enriched.py \
  >> /Users/alexcahn/Scripts/Daily_Leads/logs/daily_run.log \
  2>> /Users/alexcahn/Scripts/Daily_Leads/logs/daily_run_error.log
