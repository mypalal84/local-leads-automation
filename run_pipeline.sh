#!/bin/bash
cd /Users/alexcahn/Scripts/Daily_Leads/src || exit 1
export $(grep -v '^#' ../.env | xargs)
exec /usr/bin/python3 auto_daily_pipeline.py >> ../logs/pipeline.log 2>&1