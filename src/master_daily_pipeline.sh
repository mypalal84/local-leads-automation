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
DATA_DIR="$BASE_DIR/data"

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
# 🔀 Cross-platform deterministic shuffle helper
# ====================================================================
shuffle_pairs() {
  local input_file="$1"
  local output_file="$2"
  local seed="$3"

  if command -v shuf >/dev/null 2>&1; then
    shuf --random-source=<(printf '%s' "$seed") "$input_file" > "$output_file"
  else
    /usr/bin/python3 - "$input_file" "$output_file" "$seed" <<'PY'
import random
import sys

in_file, out_file, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(in_file, encoding="utf-8") as f:
    rows = [line.rstrip("\n") for line in f if line.strip()]
rng = random.Random(seed)
rng.shuffle(rows)
with open(out_file, "w", encoding="utf-8") as f:
    for row in rows:
        f.write(row + "\n")
PY
  fi
}

# ====================================================================
# 📁 Find latest output for a given city/service pair
# ====================================================================
find_latest_pair_output() {
  local city="$1"
  local service="$2"
  local latest=""

  latest=$(ls -t "$DATA_DIR"/no_website_emails_"$city"_"$service"_*.csv 2>/dev/null | head -n 1)
  echo "$latest"
}

# ====================================================================
# 🏁 Start
# ====================================================================
mkdir -p "$LOG_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  log "[FATAL] Missing env file: $ENV_FILE" | tee -a "$LOG_DIR/summary.log"
  exit 1
fi

cd "$SRC_DIR" || exit 1

set -a
source "$ENV_FILE"
set +a

EMAIL_ADDR=$DAILY_LEAD_EMAIL_SENDER
EMAIL_PASS=$DAILY_LEAD_EMAIL_PASS
NOTIFY_TO=${REPLY_NOTIFY_TO:-$EMAIL_ADDR}

if [[ -z "$EMAIL_ADDR" || -z "$EMAIL_PASS" ]]; then
  log "[FATAL] DAILY_LEAD_EMAIL_SENDER or DAILY_LEAD_EMAIL_PASS missing in .env" | tee -a "$LOG_DIR/summary.log"
  exit 1
fi

log "=== 🚀 Starting ZBA Digital Multi‑Service/Multi‑City Pipeline ===" | tee -a "$LOG_DIR/summary.log"
log "--- Random seed: $RANDOM_SEED ---" | tee -a "$LOG_DIR/summary.log"

PAIR_FILE="$LOG_DIR/.pairs.tmp"
> "$PAIR_FILE"
for service in "${SERVICES[@]}"; do
  for city in "${CITIES[@]}"; do
    echo "$service|$city" >> "$PAIR_FILE"
  done
done

shuffle_pairs "$PAIR_FILE" "$PAIR_FILE.shuf" "$RANDOM_SEED"

COUNT=0
TOTAL_PAIRS=$(wc -l < "$PAIR_FILE.shuf")

while IFS='|' read -r service city; do
  ((COUNT++))
  log "=== ▶️  [$COUNT/$TOTAL_PAIRS] Processing: $service | $city ===" | tee -a "$LOG_DIR/summary.log"

  /usr/bin/python3 "$SRC_DIR/find_no_website_emails.py" "$service" "$city" >> "$LOG_DIR/summary.log" 2>&1

  pair_csv=$(find_latest_pair_output "$city" "$service")
  if [[ -n "$pair_csv" ]]; then
    log "[INFO] Sending outreach from: $(basename "$pair_csv")" | tee -a "$LOG_DIR/email.log"
    /usr/bin/python3 "$SRC_DIR/send_cold_emails.py" "$pair_csv" >> "$LOG_DIR/email.log" 2>&1
  else
    log "[WARN] No verified output file found for $service | $city; skipping send step." | tee -a "$LOG_DIR/summary.log"
  fi

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

/usr/bin/python3 - <<END
import os, smtplib, ssl
from email.mime.text import MIMEText
sender = os.environ.get("DAILY_LEAD_EMAIL_SENDER")
password = os.environ.get("DAILY_LEAD_EMAIL_PASS")
receiver = os.environ.get("REPLY_NOTIFY_TO", sender)
if not sender or not password:
  raise SystemExit("Missing DAILY_LEAD_EMAIL_SENDER or DAILY_LEAD_EMAIL_PASS")
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