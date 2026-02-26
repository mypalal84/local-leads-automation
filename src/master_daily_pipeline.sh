#!/opt/homebrew/bin/bash
# ====================================================================
# ZBA Digital - Master Daily Pipeline (ASCII Clean, Bash 5.3)
# ====================================================================
# • Randomly selects 3 services + 3 cities (multi-word safe)
# • Pairs one service ↔ one city (3 jobs per run)
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
readarray -t SEL_SERVICES < <(printf "%s\n" "${SERVICES[@]}" | sort -R | head -n 3)
readarray -t SEL_CITIES   < <(printf "%s\n" "${CITIES[@]}"   | sort -R | head -n 3)

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
for i in {0..2}; do
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

while IFS='|' read -r service city; do
  ((COUNT++))
  log "--- [$COUNT/$TOTAL] $service | $city ---" | tee -a "$LOG_DIR/summary.log"

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
    if ! /usr/bin/python3 "$SRC_DIR/find_no_website_emails.py" "$service" "$city" >>"$LOG_DIR/summary.log" 2>&1; then
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