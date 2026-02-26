#!/opt/homebrew/bin/bash
# ====================================================================
# ZBA Digital - Master Daily Pipeline (ASCII Clean, Bash 5.3)
# ====================================================================
# • Randomly selects dynamic service/city pairs (multi-word safe)
# • Pair count adapts to remaining daily quota
# • Runs Discovery → Enrichment → Outreach
# • Sends daily summary email
# ====================================================================

# Locale and paths ---------------------------------------------------
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

BASE_DIR="$HOME/Scripts/Daily_Leads"
SRC_DIR="$BASE_DIR/src"
LOG_DIR="$BASE_DIR/logs"
ENV_FILE="$BASE_DIR/.env"
DATA_DIR="$BASE_DIR/data"
DAILY_EMAIL_TARGET="${DAILY_EMAIL_TARGET:-50}"
ENRICH_BUFFER_MULTIPLIER="${ENRICH_BUFFER_MULTIPLIER:-2}"
EXPECTED_SENDS_PER_PAIR="${EXPECTED_SENDS_PER_PAIR:-5}"
MAX_PAIRS_PER_RUN="${MAX_PAIRS_PER_RUN:-15}"
PIPELINE_DELAY_BETWEEN_RUNS="${PIPELINE_DELAY_BETWEEN_RUNS:-}"
DELAY_BETWEEN_RUNS="${PIPELINE_DELAY_BETWEEN_RUNS:-${DELAY_BETWEEN_RUNS:-60}}"
DRY_RUN="${DRY_RUN:-false}"

shopt -s nocasematch
if [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" || "$DRY_RUN" == "yes" ]]; then
  DRY_RUN="true"
else
  DRY_RUN="false"
fi
shopt -u nocasematch

mkdir -p "$LOG_DIR" "$DATA_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

sanitize_for_filename() {
  echo "$1" | sed -E 's/[^A-Za-z0-9_]+/_/g; s/^_+//; s/_+$//'
}

today_sent_count() {
  local daily_file="$DATA_DIR/daily_sent_$(date +%Y-%m-%d).csv"
  if [[ -f "$daily_file" ]]; then
    wc -l < "$daily_file" | awk '{print $1}'
  else
    echo 0
  fi
}

# Services ------------------------------------------------------------
SERVICES=(
"Plumbers" "Roofers" "Electricians" "Contractors / General Contractors"
"Landscapers / Lawn Care" "HVAC / Heating & Cooling" "Pest Control"
"Pool Maintenance / Repair" "Appliance Repair" "Handyman Services"
"Window Cleaning" "Garage Door Services" "Fence Installation / Repair"
"Carpet / Floor Cleaning" "Dentists" "Chiropractors" "Massage Therapists"
"Physical Therapy Clinics" "Acupuncturists" "Personal Trainers / Fitness Coaches"
"Yoga / Pilates Studios" "Martial Arts Schools" "Speech Therapists"
"Dietitians / Nutritionists" "Auto Repair / Mechanics" "Towing Services"
"Car Wash / Detailing" "Auto Body / Paint Shops" "Moving Companies"
"Storage Facilities (local)" "Lawyers (solo or small firms)" "Accountants / CPAs"
"Notaries" "Tax Preparation Services" "Insurance Agents / Brokers"
"Real Estate Agents (solo)" "Home Inspectors" "Hair Salons / Barbershops"
"Nail Salons / Beauty Services" "Pet Grooming / Pet Care"
"Dog Walking / Pet Sitting" "Event Planners / Party Rentals"
"Photography / Videography Studios" "Tutoring / Learning Centers"
"Music / Art Teachers" "Catering (small local)" "Florists" "Tailors / Alterations"
"Dry Cleaners" "Locksmiths" "Sign Installation / Printing"
"Elevator / Lift Maintenance" "Pool / Spa Installation"
"Solar Panel Installation" "Siding Installation / Repair"
"Tree Services / Arborists" "Fence Builders" "Deck / Patio Builders"
"Window / Door Installation"
)

# Cities --------------------------------------------------------------
CITIES=(
"Seattle, WA" "Spokane, WA" "Tacoma, WA" "Portland, OR" "Eugene, OR"
"Salem, OR" "Boise, ID" "Denver, CO" "Colorado Springs, CO" "Phoenix, AZ"
"Mesa, AZ" "Tucson, AZ" "Las Vegas, NV" "Reno, NV" "Salt Lake City, UT"
"Albuquerque, NM" "Dallas, TX" "Fort Worth, TX" "Austin, TX"
"San Antonio, TX" "Houston, TX" "El Paso, TX" "Oklahoma City, OK"
"Tulsa, OK" "Kansas City, MO" "St. Louis, MO" "Omaha, NE" "Wichita, KS"
"Minneapolis, MN" "St. Paul, MN" "Des Moines, IA" "Chicago, IL"
"Indianapolis, IN" "Columbus, OH" "Cleveland, OH" "Cincinnati, OH"
"Detroit, MI" "Grand Rapids, MI" "Milwaukee, WI" "Nashville, TN"
"Memphis, TN" "Louisville, KY" "Birmingham, AL" "Atlanta, GA"
"Savannah, GA" "Charlotte, NC" "Raleigh, NC" "Greensboro, NC"
"Charleston, SC" "Columbia, SC" "Jacksonville, FL" "Orlando, FL"
"Tampa, FL" "St. Petersburg, FL" "Miami, FL" "Fort Lauderdale, FL"
"New Orleans, LA" "Little Rock, AR" "Jackson, MS" "Richmond, VA"
"Virginia Beach, VA" "Washington, DC" "Baltimore, MD" "Philadelphia, PA"
"Pittsburgh, PA" "Buffalo, NY" "Rochester, NY" "Albany, NY" "Newark, NJ"
"Jersey City, NJ" "Hartford, CT" "New Haven, CT" "Providence, RI"
"Boston, MA" "Springfield, MA" "Manchester, NH" "Portland, ME"
"Los Angeles, CA" "San Diego, CA" "San Jose, CA" "Sacramento, CA"
"Fresno, CA" "Bakersfield, CA" "Riverside, CA" "San Bernardino, CA"
"Oakland, CA" "Long Beach, CA" "Anaheim, CA" "Santa Ana, CA"
"Irvine, CA" "Chula Vista, CA" "Stockton, CA" "Modesto, CA"
"Corpus Christi, TX" "Chandler, AZ" "Scottsdale, AZ"
)

# Random selection ----------------------------------------------------
sent_today_start=$(today_sent_count)
remaining_at_start=$((DAILY_EMAIL_TARGET - sent_today_start))
if (( remaining_at_start < 0 )); then
  remaining_at_start=0
fi

if (( EXPECTED_SENDS_PER_PAIR < 1 )); then
  EXPECTED_SENDS_PER_PAIR=1
fi
if (( MAX_PAIRS_PER_RUN < 1 )); then
  MAX_PAIRS_PER_RUN=1
fi

target_pairs=$(( (remaining_at_start + EXPECTED_SENDS_PER_PAIR - 1) / EXPECTED_SENDS_PER_PAIR ))
if (( target_pairs < 1 )); then
  target_pairs=1
fi

pair_count=$target_pairs
if (( pair_count > MAX_PAIRS_PER_RUN )); then
  pair_count=$MAX_PAIRS_PER_RUN
fi
if (( pair_count > ${#SERVICES[@]} )); then
  pair_count=${#SERVICES[@]}
fi
if (( pair_count > ${#CITIES[@]} )); then
  pair_count=${#CITIES[@]}
fi

readarray -t SHUF_SERVICES < <(printf "%s\n" "${SERVICES[@]}" | sort -R)
readarray -t SHUF_CITIES   < <(printf "%s\n" "${CITIES[@]}"   | sort -R)
SEL_SERVICES=("${SHUF_SERVICES[@]:0:$pair_count}")
SEL_CITIES=("${SHUF_CITIES[@]:0:$pair_count}")

echo "=== Today's Random Selections ===" | tee -a "$LOG_DIR/summary.log"

{
  echo "Services:"
  printf "%s\n" "${SEL_SERVICES[@]}"
  echo
  echo "Cities:"
  printf "%s\n" "${SEL_CITIES[@]}"
  echo
} | tee -a "$LOG_DIR/summary.log"

PAIR_FILE="$LOG_DIR/.pairs.tmp"
> "$PAIR_FILE"
for (( i=0; i<pair_count; i++ )); do
  printf "%s|%s\n" "${SEL_SERVICES[$i]}" "${SEL_CITIES[$i]}" >> "$PAIR_FILE"
done

# Reset per-run email log so summary counts reflect this run only
: > "$LOG_DIR/email.log"

log "=== Selected Pairs ===" | tee -a "$LOG_DIR/summary.log"
cat "$PAIR_FILE" | tee -a "$LOG_DIR/summary.log"
TOTAL=$(wc -l < "$PAIR_FILE")
COUNT=0

# Main loop -----------------------------------------------------------
log "=== Starting Run ($TOTAL pairs) ===" | tee -a "$LOG_DIR/summary.log"
cd "$SRC_DIR" || exit 1
set -a; source "$ENV_FILE"; set +a
DELAY_BETWEEN_RUNS="${PIPELINE_DELAY_BETWEEN_RUNS:-${DELAY_BETWEEN_RUNS:-60}}"
log "[MODE] DRY_RUN=$DRY_RUN" | tee -a "$LOG_DIR/summary.log"
log "[LIMIT] DAILY_EMAIL_TARGET=$DAILY_EMAIL_TARGET" | tee -a "$LOG_DIR/summary.log"
log "[SCHED] remaining_at_start=$remaining_at_start, expected_per_pair=$EXPECTED_SENDS_PER_PAIR, selected_pairs=$TOTAL" | tee -a "$LOG_DIR/summary.log"

while IFS='|' read -r service city; do
  sent_today=$(today_sent_count)
  remaining_quota=$((DAILY_EMAIL_TARGET - sent_today))
  if (( remaining_quota <= 0 )); then
    log "[LIMIT] Daily target reached ($sent_today/$DAILY_EMAIL_TARGET). Stopping remaining pairs." | tee -a "$LOG_DIR/summary.log"
    break
  fi

  ((COUNT++))
  log "--- [$COUNT/$TOTAL] $service | $city ---" | tee -a "$LOG_DIR/summary.log"
  log "[LIMIT] Remaining daily quota before pair: $remaining_quota" | tee -a "$LOG_DIR/summary.log"

  # Step 1: Discovery
  log "[DISCOVERY] Finding leads without websites -> $service | $city" | tee -a "$LOG_DIR/summary.log"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY] Skipping discovery command." | tee -a "$LOG_DIR/summary.log"
  else
    if ! /usr/bin/python3 "$SRC_DIR/discover_no_website_leads.py" "$service" "$city" >>"$LOG_DIR/summary.log" 2>&1; then
      log "[WARN] Discovery failed for $service | $city" | tee -a "$LOG_DIR/summary.log"
      sleep "$DELAY_BETWEEN_RUNS"; continue
    fi
  fi

  # Step 2: Enrichment
  log "[INFO] Enriching leads for $service | $city" | tee -a "$LOG_DIR/summary.log"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY] Skipping enrichment command." | tee -a "$LOG_DIR/summary.log"
  else
    enrich_limit=$((remaining_quota * ENRICH_BUFFER_MULTIPLIER))
    if (( enrich_limit < 1 )); then
      enrich_limit=1
    fi
    if ! /usr/bin/python3 "$SRC_DIR/find_no_website_emails.py" "$service" "$city" "$enrich_limit" >>"$LOG_DIR/summary.log" 2>&1; then
      log "[ERR] Enrichment failed -> skipping outreach." | tee -a "$LOG_DIR/summary.log"
      sleep "$DELAY_BETWEEN_RUNS"; continue
    fi
  fi

  safe_city="$(sanitize_for_filename "$city")"
  safe_service="$(sanitize_for_filename "$service")"
  FILE_TAG="${safe_city}_${safe_service}"
  OUT_FILE="$DATA_DIR/leads_${FILE_TAG}_NO_WEBSITE_$(date +%Y-%m-%d).csv"
  if [[ "$DRY_RUN" == "false" && ! -f "$OUT_FILE" ]]; then
    log "[WARN] No enriched file found -> $OUT_FILE" | tee -a "$LOG_DIR/summary.log"
    sleep "$DELAY_BETWEEN_RUNS"; continue
  fi

  # Step 3: Outreach
  log "[INFO] Starting outreach for $service | $city" | tee -a "$LOG_DIR/email.log"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY] Skipping outreach command for $OUT_FILE" | tee -a "$LOG_DIR/email.log"
  else
    if ! /usr/bin/python3 "$SRC_DIR/send_cold_emails.py" "$OUT_FILE" >>"$LOG_DIR/email.log" 2>&1; then
      log "[ERR] Email send failed for $service | $city" | tee -a "$LOG_DIR/email.log"
    fi
  fi

  log "--- Sleeping ${DELAY_BETWEEN_RUNS}s ---" | tee -a "$LOG_DIR/summary.log"
  sleep "$DELAY_BETWEEN_RUNS"
done < "$PAIR_FILE"

rm -f "$PAIR_FILE"

# Summary email -------------------------------------------------------
# Build daily summary
sent_count=$(grep -c "\[SENT\]" "$LOG_DIR/email.log" 2>/dev/null || true)
reply_count=$(grep -c "\[REPLY\]" "$LOG_DIR/email.log" 2>/dev/null || true)
lead_count=$(ls "$DATA_DIR"/leads_* 2>/dev/null | wc -l | awk '{print $1}')
sent_today_end=$(today_sent_count)
remaining_quota_end=$((DAILY_EMAIL_TARGET - sent_today_end))
if (( remaining_quota_end < 0 )); then
  remaining_quota_end=0
fi

KPI_CSV="$LOG_DIR/daily_kpi.csv"
if [[ ! -f "$KPI_CSV" ]]; then
  echo "date,timestamp,dry_run,pairs_selected,pairs_processed,daily_target,sent_in_run,replies_in_run,total_lead_files,sent_today_total,remaining_quota_end" > "$KPI_CSV"
fi
echo "$(date +%Y-%m-%d),$(date '+%Y-%m-%d %H:%M:%S'),$DRY_RUN,$TOTAL,$COUNT,$DAILY_EMAIL_TARGET,${sent_count:-0},${reply_count:-0},$lead_count,$sent_today_end,$remaining_quota_end" >> "$KPI_CSV"
log "[KPI] Appended daily KPI row -> $KPI_CSV" | tee -a "$LOG_DIR/summary.log"

SUMMARY=$(cat <<EOF
Daily Pipeline Summary – $(date '+%A, %B %d, %Y')

Pairs Processed: $TOTAL
Leads Generated: $lead_count
Emails Sent: ${sent_count:-0}
Replies Detected: ${reply_count:-0}

Log files:
- Summary: $LOG_DIR/summary.log
- Email: $LOG_DIR/email.log
EOF
)

log "Sending Summary Email..." | tee -a "$LOG_DIR/summary.log"
if [[ "$DRY_RUN" == "true" ]]; then
  log "[DRY] Skipping summary email send." | tee -a "$LOG_DIR/summary.log"
else
/usr/bin/python3 - <<END
import os, smtplib, ssl
from email.mime.text import MIMEText
sender=os.getenv("DAILY_LEAD_EMAIL_SENDER")
password=os.getenv("DAILY_LEAD_EMAIL_PASS")
receiver=os.getenv("REPLY_NOTIFY_TO", sender)
if sender and password:
    msg=MIMEText("""$SUMMARY""","plain","utf-8")
    msg["Subject"]="[ZBA Digital] Daily Pipeline Summary"
    msg["From"]=sender
    msg["To"]=receiver
    ctx=ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ctx) as s:
        s.login(sender,password)
        s.sendmail(sender,[receiver],msg.as_string())
END
  fi

log "Summary Email Sent to $REPLY_NOTIFY_TO" | tee -a "$LOG_DIR/summary.log"
log "Completed $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_DIR/summary.log"