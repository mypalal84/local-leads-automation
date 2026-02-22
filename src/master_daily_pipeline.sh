#!/bin/bash
# ====================================================================
# 🚀 ZBA Digital - Master Daily Pipeline
# --------------------------------------------------------------------
# Multi-service / multi-city discovery + outreach automation.
# Randomized order, safe throttling, organized logging, and
# daily progress email summary (sent via Gmail SMTP).
# ====================================================================

# 🔧 CONFIG ------------------------------------------------------------
BASE_DIR="/Users/alexcahn/Scripts/Daily_Leads"
SRC_DIR="$BASE_DIR/src"
LOG_DIR="$BASE_DIR/logs"
ENV_FILE="$BASE_DIR/.env"

# --------------------------------------------------------------------
# 🔩 SERVICES — expand freely
# --------------------------------------------------------------------
SERVICES=(
  "hvac" "roofing" "landscaping" "electrical" "plumbing"
  "pest-control" "painting" "cleaning" "carpet-cleaning"
  "fencing" "tree-service" "window-cleaning" "pressure-washing"
  "remodeling" "flooring"
)

# --------------------------------------------------------------------
# 🌎 CITIES — add/adjust to target more local markets
# --------------------------------------------------------------------
CITIES=(
  "seattle" "portland" "san-diego" "dallas" "denver"
  "phoenix" "austin" "sacramento" "salt-lake-city" "boise"
  "tucson" "las-vegas" "spokane" "reno" "houston"
)

DELAY_BETWEEN_RUNS=45  # seconds

# Random seed for daily shuffle (rotates each run)
RANDOM_SEED=$(date +%s)

# ====================================================================
# 🧠 Logging Helper
# ====================================================================
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ====================================================================
# 🏁 Start
# ====================================================================
cd "$SRC_DIR" || exit
source "$ENV_FILE"

EMAIL_ADDR=$DAILY_LEAD_EMAIL_SENDER
EMAIL_PASS=$DAILY_LEAD_EMAIL_PASS
NOTIFY_TO=${REPLY_NOTIFY_TO:-$EMAIL_ADDR}

log "=== 🚀 Starting ZBA Digital Multi‑Service/Multi‑City Pipeline ===" | tee -a "$LOG_DIR/summary.log"
log "--- Random seed: $RANDOM_SEED ---" | tee -a "$LOG_DIR/summary.log"

PAIR_FILE="$LOG_DIR/.pairs.tmp"
> "$PAIR_FILE"
for service in "${SERVICES[@]}"; do
  for city in "${CITIES[@]}"; do
    echo "$service|$city" >> "$PAIR_FILE"
  done
done

shuf --random-source=<(printf '%s' "$RANDOM_SEED") "$PAIR_FILE" > "$PAIR_FILE.shuf"

COUNT=0
TOTAL_PAIRS=$(wc -l < "$PAIR_FILE.shuf")

while IFS='|' read -r service city; do
  ((COUNT++))
  log "=== ▶️  [$COUNT/$TOTAL_PAIRS] Processing: $service | $city ===" | tee -a "$LOG_DIR/summary.log"

  /usr/bin/python3 "$SRC_DIR/find_no_website_emails.py" "$service" "$city" >> "$LOG_DIR/summary.log" 2>&1
  /usr/bin/python3 "$SRC_DIR/send_cold_emails.py" >> "$LOG_DIR/email.log" 2>&1

  log "--- Sleeping ${DELAY_BETWEEN_RUNS}s before next pair ---" | tee -a "$LOG_DIR/summary.log"
  sleep "$DELAY_BETWEEN_RUNS"
done < "$PAIR_FILE.shuf"

rm -f "$PAIR_FILE" "$PAIR_FILE.shuf"

# ====================================================================
# 📊 Daily Summary Email
# ====================================================================
log "📧 Preparing daily progress email summary..." | tee -a "$LOG_DIR/summary.log"

SUMMARY_TEXT=$(cat <<EOF
Daily Automation Summary - $(date '+%A, %B %d, %Y')

✅ Total city/service campaigns: $TOTAL_PAIRS
📁 Lead CSV files generated: $(ls "$BASE_DIR/data"/no_website_emails_* 2>/dev/null | wc -l)
✉️ Emails sent today: $(grep -c "\[SENT\]" "$LOG_DIR/email.log" 2>/dev/null || echo 0)
💬 Replies detected: $(grep -c "\[REPLY\]" "$LOG_DIR/email.log" 2>/dev/null || echo 0)

Logs:
- Summary: $LOG_DIR/summary.log
- Email:   $LOG_DIR/email.log

Have a productive day!
-- ZBA Digital Automation
EOF
)

python3 - <<END
import os, smtplib, ssl
from email.mime.text import MIMEText
sender = os.environ.get("DAILY_LEAD_EMAIL_SENDER")
password = os.environ.get("DAILY_LEAD_EMAIL_PASS")
receiver = os.environ.get("REPLY_NOTIFY_TO", sender)
body = """$SUMMARY_TEXT"""
msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = "[ZBA Digital] Daily Pipeline Summary"
msg["From"] = sender
msg["To"] = receiver
context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as s:
    s.login(sender, password)
    s.sendmail(sender, [receiver], msg.as_string())
END

log "✅ Summary email sent to $NOTIFY_TO" | tee -a "$LOG_DIR/summary.log"
log "--- Finished at $(date '+%Y-%m-%d %H:%M:%S') ---" | tee -a "$LOG_DIR/summary.log"