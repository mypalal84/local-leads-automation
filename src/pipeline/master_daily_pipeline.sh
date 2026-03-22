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
DATA_ROOT_DIR="$BASE_DIR/data"
DATA_DIR="$DATA_ROOT_DIR/current"
PROJECT_VENV_PY="$BASE_DIR/.venv/bin/python"
WORKSPACE_VENV_PY="$HOME/Scripts/.venv/bin/python"

if [[ -n "$VIRTUAL_ENV" && -x "$VIRTUAL_ENV/bin/python" ]]; then
  PYTHON_BIN="$VIRTUAL_ENV/bin/python"
elif [[ -x "$PROJECT_VENV_PY" ]]; then
  PYTHON_BIN="$PROJECT_VENV_PY"
elif [[ -x "$WORKSPACE_VENV_PY" ]]; then
  PYTHON_BIN="$WORKSPACE_VENV_PY"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  PYTHON_BIN="/usr/bin/python3"
fi

OVERRIDE_DAILY_EMAIL_TARGET=""
OVERRIDE_ENRICH_BUFFER_MULTIPLIER=""
OVERRIDE_EXPECTED_SENDS_PER_PAIR=""
OVERRIDE_MAX_PAIRS_PER_RUN=""
OVERRIDE_PIPELINE_DELAY_BETWEEN_RUNS=""
OVERRIDE_DRY_RUN=""
OVERRIDE_LEAD_SCORE_THRESHOLD=""
OVERRIDE_MAX_EMAILS_PER_DOMAIN=""
OVERRIDE_BLOCK_GENERIC_INBOXES=""
OVERRIDE_PRE_SEND_VALIDATE_EMAILS=""
OVERRIDE_CACHE_TTL_DAYS=""
OVERRIDE_PRE_ENRICH_SCORE_FILTER=""
OVERRIDE_PAIR_SUPPRESSION_ENABLED=""
OVERRIDE_STOP_WHEN_HUNTER_CALLS_STALL=""

ORIG_DAILY_EMAIL_TARGET=""
ORIG_ENRICH_BUFFER_MULTIPLIER=""
ORIG_EXPECTED_SENDS_PER_PAIR=""
ORIG_MAX_PAIRS_PER_RUN=""
ORIG_PIPELINE_DELAY_BETWEEN_RUNS=""
ORIG_DRY_RUN=""
ORIG_LEAD_SCORE_THRESHOLD=""
ORIG_MAX_EMAILS_PER_DOMAIN=""
ORIG_BLOCK_GENERIC_INBOXES=""
ORIG_PRE_SEND_VALIDATE_EMAILS=""
ORIG_CACHE_TTL_DAYS=""
ORIG_PRE_ENRICH_SCORE_FILTER=""
ORIG_PAIR_SUPPRESSION_ENABLED=""
ORIG_STOP_WHEN_HUNTER_CALLS_STALL=""

if [[ ${DAILY_EMAIL_TARGET+x} ]]; then OVERRIDE_DAILY_EMAIL_TARGET="1"; ORIG_DAILY_EMAIL_TARGET="$DAILY_EMAIL_TARGET"; fi
if [[ ${ENRICH_BUFFER_MULTIPLIER+x} ]]; then OVERRIDE_ENRICH_BUFFER_MULTIPLIER="1"; ORIG_ENRICH_BUFFER_MULTIPLIER="$ENRICH_BUFFER_MULTIPLIER"; fi
if [[ ${EXPECTED_SENDS_PER_PAIR+x} ]]; then OVERRIDE_EXPECTED_SENDS_PER_PAIR="1"; ORIG_EXPECTED_SENDS_PER_PAIR="$EXPECTED_SENDS_PER_PAIR"; fi
if [[ ${MAX_PAIRS_PER_RUN+x} ]]; then OVERRIDE_MAX_PAIRS_PER_RUN="1"; ORIG_MAX_PAIRS_PER_RUN="$MAX_PAIRS_PER_RUN"; fi
if [[ ${PIPELINE_DELAY_BETWEEN_RUNS+x} ]]; then OVERRIDE_PIPELINE_DELAY_BETWEEN_RUNS="1"; ORIG_PIPELINE_DELAY_BETWEEN_RUNS="$PIPELINE_DELAY_BETWEEN_RUNS"; fi
if [[ ${DRY_RUN+x} ]]; then OVERRIDE_DRY_RUN="1"; ORIG_DRY_RUN="$DRY_RUN"; fi
if [[ ${LEAD_SCORE_THRESHOLD+x} ]]; then OVERRIDE_LEAD_SCORE_THRESHOLD="1"; ORIG_LEAD_SCORE_THRESHOLD="$LEAD_SCORE_THRESHOLD"; fi
if [[ ${MAX_EMAILS_PER_DOMAIN+x} ]]; then OVERRIDE_MAX_EMAILS_PER_DOMAIN="1"; ORIG_MAX_EMAILS_PER_DOMAIN="$MAX_EMAILS_PER_DOMAIN"; fi
if [[ ${BLOCK_GENERIC_INBOXES+x} ]]; then OVERRIDE_BLOCK_GENERIC_INBOXES="1"; ORIG_BLOCK_GENERIC_INBOXES="$BLOCK_GENERIC_INBOXES"; fi
if [[ ${PRE_SEND_VALIDATE_EMAILS+x} ]]; then OVERRIDE_PRE_SEND_VALIDATE_EMAILS="1"; ORIG_PRE_SEND_VALIDATE_EMAILS="$PRE_SEND_VALIDATE_EMAILS"; fi
if [[ ${CACHE_TTL_DAYS+x} ]]; then OVERRIDE_CACHE_TTL_DAYS="1"; ORIG_CACHE_TTL_DAYS="$CACHE_TTL_DAYS"; fi
if [[ ${PRE_ENRICH_SCORE_FILTER+x} ]]; then OVERRIDE_PRE_ENRICH_SCORE_FILTER="1"; ORIG_PRE_ENRICH_SCORE_FILTER="$PRE_ENRICH_SCORE_FILTER"; fi
if [[ ${PAIR_SUPPRESSION_ENABLED+x} ]]; then OVERRIDE_PAIR_SUPPRESSION_ENABLED="1"; ORIG_PAIR_SUPPRESSION_ENABLED="$PAIR_SUPPRESSION_ENABLED"; fi
if [[ ${STOP_WHEN_HUNTER_CALLS_STALL+x} ]]; then OVERRIDE_STOP_WHEN_HUNTER_CALLS_STALL="1"; ORIG_STOP_WHEN_HUNTER_CALLS_STALL="$STOP_WHEN_HUNTER_CALLS_STALL"; fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

# Optional centralized config layer (config/config.yaml) for non-secret tunables.
CONFIG_RENDERER="$SRC_DIR/utils/render_config_env.py"
if [[ -f "$CONFIG_RENDERER" ]]; then
  # shellcheck disable=SC1090
  source <("$PYTHON_BIN" "$CONFIG_RENDERER")
fi

if [[ -n "$OVERRIDE_DAILY_EMAIL_TARGET" ]]; then DAILY_EMAIL_TARGET="$ORIG_DAILY_EMAIL_TARGET"; fi
if [[ -n "$OVERRIDE_ENRICH_BUFFER_MULTIPLIER" ]]; then ENRICH_BUFFER_MULTIPLIER="$ORIG_ENRICH_BUFFER_MULTIPLIER"; fi
if [[ -n "$OVERRIDE_EXPECTED_SENDS_PER_PAIR" ]]; then EXPECTED_SENDS_PER_PAIR="$ORIG_EXPECTED_SENDS_PER_PAIR"; fi
if [[ -n "$OVERRIDE_MAX_PAIRS_PER_RUN" ]]; then MAX_PAIRS_PER_RUN="$ORIG_MAX_PAIRS_PER_RUN"; fi
if [[ -n "$OVERRIDE_PIPELINE_DELAY_BETWEEN_RUNS" ]]; then PIPELINE_DELAY_BETWEEN_RUNS="$ORIG_PIPELINE_DELAY_BETWEEN_RUNS"; fi
if [[ -n "$OVERRIDE_DRY_RUN" ]]; then DRY_RUN="$ORIG_DRY_RUN"; fi
if [[ -n "$OVERRIDE_LEAD_SCORE_THRESHOLD" ]]; then LEAD_SCORE_THRESHOLD="$ORIG_LEAD_SCORE_THRESHOLD"; fi
if [[ -n "$OVERRIDE_MAX_EMAILS_PER_DOMAIN" ]]; then MAX_EMAILS_PER_DOMAIN="$ORIG_MAX_EMAILS_PER_DOMAIN"; fi
if [[ -n "$OVERRIDE_BLOCK_GENERIC_INBOXES" ]]; then BLOCK_GENERIC_INBOXES="$ORIG_BLOCK_GENERIC_INBOXES"; fi
if [[ -n "$OVERRIDE_PRE_SEND_VALIDATE_EMAILS" ]]; then PRE_SEND_VALIDATE_EMAILS="$ORIG_PRE_SEND_VALIDATE_EMAILS"; fi
if [[ -n "$OVERRIDE_CACHE_TTL_DAYS" ]]; then CACHE_TTL_DAYS="$ORIG_CACHE_TTL_DAYS"; fi
if [[ -n "$OVERRIDE_PRE_ENRICH_SCORE_FILTER" ]]; then PRE_ENRICH_SCORE_FILTER="$ORIG_PRE_ENRICH_SCORE_FILTER"; fi
if [[ -n "$OVERRIDE_PAIR_SUPPRESSION_ENABLED" ]]; then PAIR_SUPPRESSION_ENABLED="$ORIG_PAIR_SUPPRESSION_ENABLED"; fi
if [[ -n "$OVERRIDE_STOP_WHEN_HUNTER_CALLS_STALL" ]]; then STOP_WHEN_HUNTER_CALLS_STALL="$ORIG_STOP_WHEN_HUNTER_CALLS_STALL"; fi

: "${DAILY_EMAIL_TARGET:=50}"
: "${ENRICH_BUFFER_MULTIPLIER:=2}"
: "${MAX_ENRICH_LEADS_PER_PAIR:=0}"
: "${EXPECTED_SENDS_PER_PAIR:=5}"
: "${ADAPTIVE_PAIR_SCHEDULING:=false}"
: "${ADAPTIVE_LOOKBACK_RUNS:=5}"
: "${ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR:=2}"
: "${ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR:=8}"
: "${ADAPTIVE_SAFETY_FACTOR:=1.0}"
: "${MAX_PAIRS_PER_RUN:=15}"
: "${ZERO_SEND_STREAK_STOP:=0}"
: "${PARALLEL_DISCOVERY_ENABLED:=true}"
: "${PARALLEL_DISCOVERY_MAX_JOBS:=3}"
: "${PARALLEL_DISCOVERY_STAGGER_SEC:=3}"
: "${PIPELINE_DELAY_BETWEEN_RUNS:=}"
: "${LOG_ARCHIVE_RETENTION_DAYS:=60}"
: "${DRY_RUN:=false}"
: "${API_SUCCESS_RATE_ALERT_THRESHOLD:=90}"
: "${EFFICIENCY_MIN_EMAILS_PER_API_CALL:=0.2}"
: "${GOOGLE_TEXT_SEARCH_ENTERPRISE_PRICE_PER_1000:=35}"
: "${GOOGLE_PLACE_DETAILS_ENTERPRISE_PRICE_PER_1000:=20}"
: "${GOOGLE_MONTHLY_PROJECTED_COST_ALERT_THRESHOLD:=0}"
: "${LOG_ROTATE_MAX_MB:=10}"

DELAY_BETWEEN_RUNS="${PIPELINE_DELAY_BETWEEN_RUNS:-${DELAY_BETWEEN_RUNS:-60}}"

shopt -s nocasematch
if [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" || "$DRY_RUN" == "yes" ]]; then
  DRY_RUN="true"
else
  DRY_RUN="false"
fi
if [[ "$ADAPTIVE_PAIR_SCHEDULING" == "1" || "$ADAPTIVE_PAIR_SCHEDULING" == "true" || "$ADAPTIVE_PAIR_SCHEDULING" == "yes" ]]; then
  ADAPTIVE_PAIR_SCHEDULING="true"
else
  ADAPTIVE_PAIR_SCHEDULING="false"
fi
if [[ "$PARALLEL_DISCOVERY_ENABLED" == "1" || "$PARALLEL_DISCOVERY_ENABLED" == "true" || "$PARALLEL_DISCOVERY_ENABLED" == "yes" ]]; then
  PARALLEL_DISCOVERY_ENABLED="true"
else
  PARALLEL_DISCOVERY_ENABLED="false"
fi
shopt -u nocasematch

if ! [[ "$PARALLEL_DISCOVERY_MAX_JOBS" =~ ^[0-9]+$ ]] || (( PARALLEL_DISCOVERY_MAX_JOBS < 1 )); then
  PARALLEL_DISCOVERY_MAX_JOBS=1
fi

RUN_METRICS_DIR="$LOG_DIR/run_metrics"
mkdir -p "$LOG_DIR" "$DATA_DIR" "$RUN_METRICS_DIR"

archive_run_metrics_files() {
  local archive_stamp="$1"
  local archive_session_dir="$LOG_DIR/archive/$archive_stamp"
  local moved=0

  shopt -s nullglob
  local metrics_files=(
    "$RUN_METRICS_DIR"/run_metrics_*.json
    "$LOG_DIR"/run_metrics_*.json
  )
  shopt -u nullglob

  if (( ${#metrics_files[@]} == 0 )); then
    return
  fi

  mkdir -p "$archive_session_dir"

  for metrics_path in "${metrics_files[@]}"; do
    if mv "$metrics_path" "$archive_session_dir/" 2>/dev/null; then
      ((moved++))
    fi
  done

  if (( moved > 0 )); then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ARCHIVE] Moved $moved run_metrics file(s) -> $archive_session_dir"
  fi
}

prune_old_metrics_archives() {
  local retention_days="$LOG_ARCHIVE_RETENTION_DAYS"
  local archive_root="$LOG_DIR/archive"

  if ! [[ "$retention_days" =~ ^[0-9]+$ ]]; then
    retention_days=60
  fi
  if (( retention_days <= 0 )); then
    return
  fi
  if [[ ! -d "$archive_root" ]]; then
    return
  fi

  local old_dirs=()
  while IFS= read -r dir; do
    old_dirs+=("$dir")
  done < <(find "$archive_root" -mindepth 1 -maxdepth 1 -type d -mtime +"$retention_days" 2>/dev/null)

  if (( ${#old_dirs[@]} == 0 )); then
    return
  fi

  local removed=0
  for dir in "${old_dirs[@]}"; do
    if rm -rf "$dir"; then
      ((removed++))
    fi
  done

  if (( removed > 0 )); then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ARCHIVE] Pruned $removed archive folder(s) older than ${retention_days} day(s)."
  fi
}

rotate_log_if_large() {
  local file_path="$1"
  local archive_stamp="$2"
  local max_mb="$LOG_ROTATE_MAX_MB"

  if [[ ! -f "$file_path" ]]; then
    return
  fi
  if ! [[ "$max_mb" =~ ^[0-9]+$ ]] || (( max_mb <= 0 )); then
    return
  fi

  local max_bytes=$((max_mb * 1024 * 1024))
  local file_bytes
  file_bytes=$(wc -c < "$file_path" 2>/dev/null || echo 0)
  if (( file_bytes <= max_bytes )); then
    return
  fi

  local archive_session_dir="$LOG_DIR/archive/$archive_stamp"
  mkdir -p "$archive_session_dir"
  local base_name
  base_name="$(basename "$file_path")"
  local rotated_path="$archive_session_dir/${base_name%.log}_${archive_stamp}.log"

  if mv "$file_path" "$rotated_path" 2>/dev/null; then
    : > "$file_path"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [LOG-ROTATE] Rotated $base_name (${file_bytes} bytes) -> $rotated_path"
  fi
}

RUN_ID="$(date '+%Y-%m-%d_%H-%M-%S')"
rotate_log_if_large "$LOG_DIR/summary.log" "$RUN_ID"
rotate_log_if_large "$LOG_DIR/email.log" "$RUN_ID"
rotate_log_if_large "$LOG_DIR/pytest_latest.log" "$RUN_ID"
archive_run_metrics_files "$RUN_ID"
prune_old_metrics_archives
RUN_METRICS_FILE="$RUN_METRICS_DIR/run_metrics_${RUN_ID}.json"
export PIPELINE_RUN_METRICS_FILE="$RUN_METRICS_FILE"
RUN_START_EPOCH="$(date +%s)"
DISCOVERY_DURATION_SEC=0
ENRICH_DURATION_SEC=0
OUTREACH_DURATION_SEC=0
PENDING_FILE="${PENDING_LEADS_FILE:-$DATA_DIR/pending_leads.csv}"

cat > "$RUN_METRICS_FILE" <<EOF
{
  "google_places": 0,
  "serper": 0,
  "hunter": 0,
  "google_places_calls": 0,
  "google_places_success": 0,
  "google_places_error": 0,
  "google_places_cache_hit": 0,
  "google_places_latency_ms_sum": 0,
  "google_places_latency_ms_count": 0,
  "google_places_text_search_calls": 0,
  "google_places_text_search_success": 0,
  "google_places_text_search_error": 0,
  "google_places_text_search_cache_hit": 0,
  "google_places_text_search_latency_ms_sum": 0,
  "google_places_text_search_latency_ms_count": 0,
  "google_places_details_calls": 0,
  "google_places_details_success": 0,
  "google_places_details_error": 0,
  "google_places_details_cache_hit": 0,
  "google_places_details_latency_ms_sum": 0,
  "google_places_details_latency_ms_count": 0,
  "serper_calls": 0,
  "serper_success": 0,
  "serper_error": 0,
  "serper_cache_hit": 0,
  "serper_latency_ms_sum": 0,
  "serper_latency_ms_count": 0,
  "hunter_calls": 0,
  "hunter_success": 0,
  "hunter_error": 0,
  "hunter_cache_hit": 0,
  "hunter_latency_ms_sum": 0,
  "hunter_latency_ms_count": 0
}
EOF

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

sanitize_for_filename() {
  echo "$1" | sed -E 's/[^A-Za-z0-9_]+/_/g; s/^_+//; s/_+$//'
}

today_sent_count() {
  local stamp
  stamp="$(date +%Y-%m-%d)"
  local daily_file="$DATA_DIR/daily_sent/daily_sent_${stamp}.csv"
  local legacy_daily_file="$DATA_DIR/daily_sent_${stamp}.csv"
  local root_legacy_daily_file="$DATA_ROOT_DIR/daily_sent_${stamp}.csv"

  if [[ ! -f "$daily_file" && -f "$legacy_daily_file" ]]; then
    daily_file="$legacy_daily_file"
  elif [[ ! -f "$daily_file" && -f "$root_legacy_daily_file" ]]; then
    daily_file="$root_legacy_daily_file"
  fi

  if [[ -f "$daily_file" ]]; then
    wc -l < "$daily_file" | awk '{print $1}'
  else
    echo 0
  fi
}

run_sent_count() {
  if [[ -f "$LOG_DIR/email.log" ]]; then
    grep -c "\[SENT\]" "$LOG_DIR/email.log" 2>/dev/null || true
  else
    echo 0
  fi
}

adaptive_expected_sends_per_pair() {
  local fallback="$1"
  local history_csv="$RUN_METRICS_DIR/history.csv"

  if [[ "$ADAPTIVE_PAIR_SCHEDULING" != "true" ]]; then
    echo "$fallback"
    return
  fi

  if ! [[ "$ADAPTIVE_LOOKBACK_RUNS" =~ ^[0-9]+$ ]] || (( ADAPTIVE_LOOKBACK_RUNS < 1 )); then
    ADAPTIVE_LOOKBACK_RUNS=5
  fi
  if ! [[ "$ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR" =~ ^[0-9]+$ ]] || (( ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR < 1 )); then
    ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR=1
  fi
  if ! [[ "$ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR" =~ ^[0-9]+$ ]] || (( ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR < ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR )); then
    ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR=$ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR
  fi

  if [[ ! -f "$history_csv" ]]; then
    echo "$fallback"
    return
  fi

  local computed
  computed=$(HISTORY_CSV="$history_csv" LOOKBACK="$ADAPTIVE_LOOKBACK_RUNS" FALLBACK="$fallback" ADAPTIVE_MIN="$ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR" ADAPTIVE_MAX="$ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR" ADAPTIVE_SAFETY_FACTOR="$ADAPTIVE_SAFETY_FACTOR" "$PYTHON_BIN" - <<'PY'
import csv
import os

path = os.getenv("HISTORY_CSV", "")
lookback = int(os.getenv("LOOKBACK", "5") or 5)
fallback = int(os.getenv("FALLBACK", "5") or 5)
adaptive_min = int(os.getenv("ADAPTIVE_MIN", "1") or 1)
adaptive_max = int(os.getenv("ADAPTIVE_MAX", str(adaptive_min)) or adaptive_min)
try:
    safety_factor = float(os.getenv("ADAPTIVE_SAFETY_FACTOR", "1.0") or 1.0)
except Exception:
    safety_factor = 1.0

rows = []
if path and os.path.isfile(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dry = str((row or {}).get("dry_run", "")).strip().lower()
            if dry in {"true", "1", "yes"}:
                continue
            try:
                pairs = int(float((row or {}).get("pairs_processed", 0) or 0))
                sent = int(float((row or {}).get("sent_in_run", 0) or 0))
            except Exception:
                continue
            if pairs <= 0:
                continue
            rows.append((sent, pairs))

if not rows:
    print(fallback)
    raise SystemExit

rows = rows[-max(1, lookback):]
total_sent = sum(sent for sent, _ in rows)
total_pairs = sum(pairs for _, pairs in rows)
if total_pairs <= 0:
    print(fallback)
    raise SystemExit

expected = (total_sent / total_pairs) * max(0.1, safety_factor)
rounded = int(round(expected))
clamped = max(adaptive_min, min(adaptive_max, rounded))
print(clamped)
PY
)

  if ! [[ "$computed" =~ ^[0-9]+$ ]] || (( computed < 1 )); then
    echo "$fallback"
    return
  fi

  echo "$computed"
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
"Birmingham, AL" "Montgomery, AL" "Mobile, AL"
"Chandler, AZ" "Gilbert, AZ" "Glendale, AZ" "Mesa, AZ" "Peoria, AZ" "Phoenix, AZ" "Scottsdale, AZ" "Tempe, AZ" "Tucson, AZ"
"Little Rock, AR"
"Anaheim, CA" "Bakersfield, CA" "Chula Vista, CA" "Fremont, CA" "Fresno, CA" "Irvine, CA" "Long Beach, CA" "Los Angeles, CA"
"Modesto, CA" "Oakland, CA" "Oxnard, CA" "Riverside, CA" "Sacramento, CA" "San Bernardino, CA" "San Diego, CA"
"San Jose, CA" "Santa Ana, CA" "Stockton, CA"
"Colorado Springs, CO" "Denver, CO" "Aurora, CO"
"Hartford, CT" "New Haven, CT"
"Washington, DC"
"Fort Lauderdale, FL" "Hialeah, FL" "Jacksonville, FL" "Miami, FL" "Orlando, FL" "Pembroke Pines, FL"
"Port St. Lucie, FL" "St. Petersburg, FL" "Tampa, FL"
"Atlanta, GA" "Augusta, GA" "Columbus, GA" "Savannah, GA"
"Boise, ID"
"Chicago, IL" "Naperville, IL" "Peoria, IL" "Rockford, IL" "Springfield, IL"
"Indianapolis, IN" "Fort Wayne, IN"
"Des Moines, IA"
"Overland Park, KS" "Wichita, KS"
"Lexington, KY" "Louisville, KY"
"Baton Rouge, LA" "Lafayette, LA" "New Orleans, LA" "Shreveport, LA"
"Boston, MA" "Springfield, MA"
"Baltimore, MD"
"Portland, ME"
"Detroit, MI" "Grand Rapids, MI" "Ann Arbor, MI"
"Minneapolis, MN" "St. Paul, MN"
"Kansas City, MO" "Springfield, MO" "St. Louis, MO"
"Jackson, MS"
"Bozeman, MT" "Missoula, MT"
"Charlotte, NC" "Durham, NC" "Greensboro, NC" "Raleigh, NC" "Winston-Salem, NC"
"Omaha, NE"
"Manchester, NH"
"Jersey City, NJ" "Newark, NJ" "Paterson, NJ"
"Albuquerque, NM" "Santa Fe, NM"
"Henderson, NV" "Las Vegas, NV" "North Las Vegas, NV" "Reno, NV"
"Albany, NY" "Buffalo, NY" "Rochester, NY" "Syracuse, NY" "Yonkers, NY"
"Cincinnati, OH" "Cleveland, OH" "Columbus, OH" "Toledo, OH"
"Oklahoma City, OK" "Tulsa, OK"
"Bend, OR" "Eugene, OR" "Gresham, OR" "Portland, OR" "Salem, OR"
"Philadelphia, PA" "Pittsburgh, PA"
"Providence, RI"
"Charleston, SC" "Columbia, SC"
"Sioux Falls, SD"
"Chattanooga, TN" "Clarksville, TN" "Memphis, TN" "Murfreesboro, TN" "Nashville, TN"
"Arlington, TX" "Austin, TX" "Corpus Christi, TX" "Dallas, TX" "El Paso, TX" "Fort Worth, TX" "Garland, TX" "Houston, TX"
"Irving, TX" "Lubbock, TX" "Plano, TX" "San Antonio, TX"
"Provo, UT" "Salt Lake City, UT"
"Richmond, VA" "Virginia Beach, VA"
"Seattle, WA" "Spokane, WA" "Tacoma, WA" "Vancouver, WA"
"Green Bay, WI" "Madison, WI" "Milwaukee, WI"
"Cheyenne, WY"
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
if (( MAX_ENRICH_LEADS_PER_PAIR < 0 )); then
  MAX_ENRICH_LEADS_PER_PAIR=0
fi
if (( ZERO_SEND_STREAK_STOP < 0 )); then
  ZERO_SEND_STREAK_STOP=0
fi

effective_expected_sends_per_pair="$(adaptive_expected_sends_per_pair "$EXPECTED_SENDS_PER_PAIR")"
if ! [[ "$effective_expected_sends_per_pair" =~ ^[0-9]+$ ]] || (( effective_expected_sends_per_pair < 1 )); then
  effective_expected_sends_per_pair="$EXPECTED_SENDS_PER_PAIR"
fi

target_pairs=$(( (remaining_at_start + effective_expected_sends_per_pair - 1) / effective_expected_sends_per_pair ))
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

declare -a PAIR_SERVICES
declare -a PAIR_CITIES
declare -a DISCOVERY_EXIT_CODES

while IFS='|' read -r service city; do
  PAIR_SERVICES+=("$service")
  PAIR_CITIES+=("$city")
done < "$PAIR_FILE"

# Main loop -----------------------------------------------------------
log "=== Starting Run ($TOTAL pairs) ===" | tee -a "$LOG_DIR/summary.log"
cd "$SRC_DIR" || exit 1
export PIPELINE_RUN_METRICS_FILE="$RUN_METRICS_FILE"
DELAY_BETWEEN_RUNS="${PIPELINE_DELAY_BETWEEN_RUNS:-${DELAY_BETWEEN_RUNS:-60}}"
log "[RUNTIME] PYTHON_BIN=$PYTHON_BIN" | tee -a "$LOG_DIR/summary.log"
log "[MODE] DRY_RUN=$DRY_RUN" | tee -a "$LOG_DIR/summary.log"
log "[LIMIT] DAILY_EMAIL_TARGET=$DAILY_EMAIL_TARGET" | tee -a "$LOG_DIR/summary.log"
log "[LIMIT] MAX_ENRICH_LEADS_PER_PAIR=$MAX_ENRICH_LEADS_PER_PAIR" | tee -a "$LOG_DIR/summary.log"
log "[LIMIT] ZERO_SEND_STREAK_STOP=$ZERO_SEND_STREAK_STOP" | tee -a "$LOG_DIR/summary.log"
log "[SCHED] ADAPTIVE_PAIR_SCHEDULING=$ADAPTIVE_PAIR_SCHEDULING, lookback=$ADAPTIVE_LOOKBACK_RUNS, safety_factor=$ADAPTIVE_SAFETY_FACTOR" | tee -a "$LOG_DIR/summary.log"
log "[SCHED] remaining_at_start=$remaining_at_start, expected_per_pair_base=$EXPECTED_SENDS_PER_PAIR, expected_per_pair_effective=$effective_expected_sends_per_pair, selected_pairs=$TOTAL" | tee -a "$LOG_DIR/summary.log"

zero_send_streak=0

if [[ "$DRY_RUN" == "false" && "$PARALLEL_DISCOVERY_ENABLED" == "true" ]]; then
  log "[DISCOVERY] Parallel phase enabled (max_jobs=$PARALLEL_DISCOVERY_MAX_JOBS, stagger=${PARALLEL_DISCOVERY_STAGGER_SEC}s)" | tee -a "$LOG_DIR/summary.log"
  step_started_epoch="$(date +%s)"
  declare -A PID_TO_INDEX
  running_jobs=0

  for ((i=0; i<TOTAL; i++)); do
    service="${PAIR_SERVICES[$i]}"
    city="${PAIR_CITIES[$i]}"
    log "[DISCOVERY][QUEUE] [$((i+1))/$TOTAL] $service | $city" | tee -a "$LOG_DIR/summary.log"

    while (( running_jobs >= PARALLEL_DISCOVERY_MAX_JOBS )); do
      if wait -n -p finished_pid; then
        wait_status=0
      else
        wait_status=$?
      fi
      finished_index="${PID_TO_INDEX[$finished_pid]:-}"
      if [[ -n "$finished_index" ]]; then
        DISCOVERY_EXIT_CODES[$finished_index]="$wait_status"
      fi
      running_jobs=$((running_jobs - 1))
    done

    (
      "$PYTHON_BIN" "$SRC_DIR/discovery/discover_no_website_leads.py" "$service" "$city" >>"$LOG_DIR/summary.log" 2>&1
    ) &
    pid=$!
    PID_TO_INDEX[$pid]="$i"
    running_jobs=$((running_jobs + 1))
    sleep "$PARALLEL_DISCOVERY_STAGGER_SEC"
  done

  while (( running_jobs > 0 )); do
    if wait -n -p finished_pid; then
      wait_status=0
    else
      wait_status=$?
    fi
    finished_index="${PID_TO_INDEX[$finished_pid]:-}"
    if [[ -n "$finished_index" ]]; then
      DISCOVERY_EXIT_CODES[$finished_index]="$wait_status"
    fi
    running_jobs=$((running_jobs - 1))
  done

  step_finished_epoch="$(date +%s)"
  DISCOVERY_DURATION_SEC=$((DISCOVERY_DURATION_SEC + step_finished_epoch - step_started_epoch))
else
  if [[ "$DRY_RUN" == "false" ]]; then
    log "[DISCOVERY] Parallel phase disabled; discovery will run per pair." | tee -a "$LOG_DIR/summary.log"
  fi
fi

for ((i=0; i<TOTAL; i++)); do
  service="${PAIR_SERVICES[$i]}"
  city="${PAIR_CITIES[$i]}"
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
  elif [[ "$PARALLEL_DISCOVERY_ENABLED" == "true" ]]; then
    discovery_status="${DISCOVERY_EXIT_CODES[$i]:-1}"
    if [[ "$discovery_status" != "0" ]]; then
      log "[WARN] Discovery failed for $service | $city" | tee -a "$LOG_DIR/summary.log"
      sleep "$DELAY_BETWEEN_RUNS"; continue
    fi
    log "[DISCOVERY] Reusing parallel discovery output." | tee -a "$LOG_DIR/summary.log"
  else
    step_started_epoch="$(date +%s)"
    if ! "$PYTHON_BIN" "$SRC_DIR/discovery/discover_no_website_leads.py" "$service" "$city" >>"$LOG_DIR/summary.log" 2>&1; then
      step_finished_epoch="$(date +%s)"
      DISCOVERY_DURATION_SEC=$((DISCOVERY_DURATION_SEC + step_finished_epoch - step_started_epoch))
      log "[WARN] Discovery failed for $service | $city" | tee -a "$LOG_DIR/summary.log"
      sleep "$DELAY_BETWEEN_RUNS"; continue
    fi
    step_finished_epoch="$(date +%s)"
    DISCOVERY_DURATION_SEC=$((DISCOVERY_DURATION_SEC + step_finished_epoch - step_started_epoch))
  fi

  # Step 2: Enrichment
  log "[INFO] Enriching leads for $service | $city" | tee -a "$LOG_DIR/summary.log"
  step_started_epoch="$(date +%s)"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY] Skipping enrichment command." | tee -a "$LOG_DIR/summary.log"
  else
    pairs_remaining=$((TOTAL - COUNT + 1))
    if (( pairs_remaining < 1 )); then
      pairs_remaining=1
    fi
    quota_slice=$(( (remaining_quota + pairs_remaining - 1) / pairs_remaining ))
    enrich_limit=$((quota_slice * ENRICH_BUFFER_MULTIPLIER))
    enrich_limit_uncapped=$enrich_limit
    if (( enrich_limit < 1 )); then
      enrich_limit=1
    fi
    if (( MAX_ENRICH_LEADS_PER_PAIR > 0 && enrich_limit > MAX_ENRICH_LEADS_PER_PAIR )); then
      enrich_limit=$MAX_ENRICH_LEADS_PER_PAIR
    fi
    log "[BUDGET] remaining_quota=$remaining_quota, pairs_remaining=$pairs_remaining, quota_slice=$quota_slice, enrich_limit=$enrich_limit (uncapped=$enrich_limit_uncapped)" | tee -a "$LOG_DIR/summary.log"
    if ! "$PYTHON_BIN" "$SRC_DIR/enrichment/enrich_leads.py" "$service" "$city" "$enrich_limit" >>"$LOG_DIR/summary.log" 2>&1; then
      step_finished_epoch="$(date +%s)"
      ENRICH_DURATION_SEC=$((ENRICH_DURATION_SEC + step_finished_epoch - step_started_epoch))
      log "[ERR] Enrichment failed -> skipping outreach." | tee -a "$LOG_DIR/summary.log"
      sleep "$DELAY_BETWEEN_RUNS"; continue
    fi
  fi
  step_finished_epoch="$(date +%s)"
  ENRICH_DURATION_SEC=$((ENRICH_DURATION_SEC + step_finished_epoch - step_started_epoch))

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
  step_started_epoch="$(date +%s)"
  sent_before_pair=$(run_sent_count)
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY] Skipping outreach command for $OUT_FILE" | tee -a "$LOG_DIR/email.log"
  else
    if ! "$PYTHON_BIN" "$SRC_DIR/outreach/send_cold_emails.py" "$OUT_FILE" >>"$LOG_DIR/email.log" 2>&1; then
      log "[ERR] Email send failed for $service | $city" | tee -a "$LOG_DIR/email.log"
    fi
  fi
  sent_after_pair=$(run_sent_count)
  pair_sent_delta=$((sent_after_pair - sent_before_pair))
  if (( pair_sent_delta < 0 )); then
    pair_sent_delta=0
  fi
  step_finished_epoch="$(date +%s)"
  OUTREACH_DURATION_SEC=$((OUTREACH_DURATION_SEC + step_finished_epoch - step_started_epoch))

  log "[PAIR-RESULT] sent_delta=$pair_sent_delta for $service | $city" | tee -a "$LOG_DIR/summary.log"
  if [[ "$DRY_RUN" == "false" ]]; then
    if (( pair_sent_delta <= 0 )); then
      zero_send_streak=$((zero_send_streak + 1))
      log "[PAIR-RESULT] zero_send_streak=$zero_send_streak" | tee -a "$LOG_DIR/summary.log"
    else
      zero_send_streak=0
    fi

    if (( ZERO_SEND_STREAK_STOP > 0 && zero_send_streak >= ZERO_SEND_STREAK_STOP )); then
      log "[LIMIT] Zero-send streak reached ($zero_send_streak). Stopping remaining pairs." | tee -a "$LOG_DIR/summary.log"
      break
    fi
  fi

  log "--- Sleeping ${DELAY_BETWEEN_RUNS}s ---" | tee -a "$LOG_DIR/summary.log"
  sleep "$DELAY_BETWEEN_RUNS"
done

rm -f "$PAIR_FILE"

# Summary email -------------------------------------------------------
# Build daily summary
sent_count=$(grep -c "\[SENT\]" "$LOG_DIR/email.log" 2>/dev/null || true)
reply_count=$(grep -c "\[REPLY\]" "$LOG_DIR/email.log" 2>/dev/null || true)
hard_bounce_count=$(grep -c "\[BOUNCE\] Hard bounce" "$LOG_DIR/email.log" 2>/dev/null || true)
soft_bounce_count=$(grep -c "\[BOUNCE\] soft bounce" "$LOG_DIR/email.log" 2>/dev/null || true)
lead_count=$(ls "$DATA_DIR"/leads_* 2>/dev/null | wc -l | awk '{print $1}')
sent_today_end=$(today_sent_count)
remaining_quota_end=$((DAILY_EMAIL_TARGET - sent_today_end))
RUN_END_EPOCH="$(date +%s)"
RUN_DURATION_SEC=$((RUN_END_EPOCH - RUN_START_EPOCH))
if (( remaining_quota_end < 0 )); then
  remaining_quota_end=0
fi

pending_queue_size_end=0
if [[ -f "$PENDING_FILE" ]]; then
  pending_lines=$(wc -l < "$PENDING_FILE" | awk '{print $1}')
  if (( pending_lines > 0 )); then
    pending_queue_size_end=$((pending_lines - 1))
  fi
fi

TODAY_SENT_LOG="$DATA_DIR/daily_sent/daily_sent_$(date +%Y-%m-%d).csv"
SEND_AUDIT_JSON=""
SEND_AUDIT_CSV=""
if [[ -f "$TODAY_SENT_LOG" ]]; then
  if audit_output=$("$PYTHON_BIN" "$SRC_DIR/generate_send_audit.py" \
    --base-dir "$BASE_DIR" \
    --daily-sent "$TODAY_SENT_LOG" \
    --run-id "$RUN_ID" \
    --output-dir "$RUN_METRICS_DIR" 2>&1); then
    log "$audit_output" | tee -a "$LOG_DIR/summary.log"
    SEND_AUDIT_JSON="$RUN_METRICS_DIR/send_audit_${RUN_ID}.json"
    SEND_AUDIT_CSV="$RUN_METRICS_DIR/send_audit_${RUN_ID}.csv"
  else
    log "[WARN] Send audit generation failed: $audit_output" | tee -a "$LOG_DIR/summary.log"
  fi
else
  log "[WARN] Send audit skipped: daily sent ledger not found at $TODAY_SENT_LOG" | tee -a "$LOG_DIR/summary.log"
fi

RUN_HISTORY_CSV="$RUN_METRICS_DIR/history.csv"

metrics_snapshot=$(RUN_SENT_COUNT="$sent_count" RUN_HISTORY_CSV="$RUN_HISTORY_CSV" GOOGLE_TEXT_PRICE_PER_1000="$GOOGLE_TEXT_SEARCH_ENTERPRISE_PRICE_PER_1000" GOOGLE_DETAILS_PRICE_PER_1000="$GOOGLE_PLACE_DETAILS_ENTERPRISE_PRICE_PER_1000" "$PYTHON_BIN" - <<END
import json, os
import csv
from datetime import datetime
import calendar

path = os.getenv("PIPELINE_RUN_METRICS_FILE", "")
run_history_csv = os.getenv("RUN_HISTORY_CSV", "")
sent_in_run = int(os.getenv("RUN_SENT_COUNT", "0") or 0)
google_text_price_per_1000 = float(os.getenv("GOOGLE_TEXT_PRICE_PER_1000", "35") or 35)
google_details_price_per_1000 = float(os.getenv("GOOGLE_DETAILS_PRICE_PER_1000", "20") or 20)

keys = {
    "google_places": 0,
    "serper": 0,
    "hunter": 0,
    "google_places_calls": 0,
    "google_places_success": 0,
    "google_places_error": 0,
    "google_places_cache_hit": 0,
    "google_places_latency_ms_sum": 0,
    "google_places_latency_ms_count": 0,
    "google_places_text_search_calls": 0,
    "google_places_text_search_success": 0,
    "google_places_text_search_error": 0,
    "google_places_text_search_cache_hit": 0,
    "google_places_text_search_latency_ms_sum": 0,
    "google_places_text_search_latency_ms_count": 0,
    "google_places_details_calls": 0,
    "google_places_details_success": 0,
    "google_places_details_error": 0,
    "google_places_details_cache_hit": 0,
    "google_places_details_latency_ms_sum": 0,
    "google_places_details_latency_ms_count": 0,
    "serper_calls": 0,
    "serper_success": 0,
    "serper_error": 0,
    "serper_cache_hit": 0,
    "serper_latency_ms_sum": 0,
    "serper_latency_ms_count": 0,
    "hunter_calls": 0,
    "hunter_success": 0,
    "hunter_error": 0,
    "hunter_cache_hit": 0,
    "hunter_latency_ms_sum": 0,
    "hunter_latency_ms_count": 0,
}

if path and os.path.isfile(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for k in keys:
            keys[k] = int(loaded.get(k, 0) or 0)
    except Exception:
        pass

now = datetime.now()
month_prefix = now.strftime("%Y-%m")

def as_int(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0

prior_text_calls_mtd = 0
prior_details_calls_mtd = 0
if run_history_csv and os.path.isfile(run_history_csv):
    try:
        with open(run_history_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = (row or {}).get("timestamp", "")
                if not ts.startswith(month_prefix):
                    continue
                prior_text_calls_mtd += as_int(row.get("google_places_text_search_calls", 0))
                prior_details_calls_mtd += as_int(row.get("google_places_details_calls", 0))
    except Exception:
        pass

def tiered_cost(calls, tiers):
    # tiers: list of (start_inclusive, end_exclusive_or_none, price_per_1000)
    remaining = max(0, int(calls))
    total = 0.0
    for start, end, price in tiers:
        if remaining <= start:
            continue
        upper = remaining if end is None else min(remaining, end)
        units = max(0, upper - start)
        if units:
            total += (units / 1000.0) * float(price)
    return total

text_tiers = [
    (0, 1000, 0.0),
    (1000, 100000, google_text_price_per_1000),
    (100000, 500000, 28.0),
    (500000, 1000000, 21.0),
    (1000000, 5000000, 10.5),
    (5000000, None, 2.63),
]
details_tiers = [
    (0, 1000, 0.0),
    (1000, 100000, google_details_price_per_1000),
    (100000, 500000, 16.0),
    (500000, 1000000, 12.0),
    (1000000, 5000000, 6.0),
    (5000000, None, 1.51),
]

api_calls_total = keys["google_places_calls"] + keys["serper_calls"] + keys["hunter_calls"]
api_success_total = keys["google_places_success"] + keys["serper_success"] + keys["hunter_success"]
api_error_total = keys["google_places_error"] + keys["serper_error"] + keys["hunter_error"]
cache_hits_total = keys["google_places_cache_hit"] + keys["serper_cache_hit"] + keys["hunter_cache_hit"]
api_success_rate = (100.0 * api_success_total / api_calls_total) if api_calls_total else 0.0
cache_hit_rate = (100.0 * cache_hits_total / (api_calls_total + cache_hits_total)) if (api_calls_total + cache_hits_total) else 0.0
emails_per_api_call = (float(sent_in_run) / api_calls_total) if api_calls_total else 0.0
google_text_calls = keys["google_places_text_search_calls"]
google_details_calls = keys["google_places_details_calls"]
text_calls_mtd_after = prior_text_calls_mtd + google_text_calls
details_calls_mtd_after = prior_details_calls_mtd + google_details_calls
text_cost_mtd_before = tiered_cost(prior_text_calls_mtd, text_tiers)
details_cost_mtd_before = tiered_cost(prior_details_calls_mtd, details_tiers)
text_cost_mtd_after = tiered_cost(text_calls_mtd_after, text_tiers)
details_cost_mtd_after = tiered_cost(details_calls_mtd_after, details_tiers)
google_cost_estimated_run = (text_cost_mtd_after + details_cost_mtd_after) - (text_cost_mtd_before + details_cost_mtd_before)
google_cost_estimated_mtd = text_cost_mtd_after + details_cost_mtd_after
days_in_month = calendar.monthrange(now.year, now.month)[1]
elapsed_days = max(1, now.day)
google_cost_estimated_monthly_projected = (google_cost_estimated_mtd / elapsed_days) * days_in_month
emails_per_google_dollar = (float(sent_in_run) / google_cost_estimated_run) if google_cost_estimated_run > 0 else 0.0

def avg_latency(provider):
    count = keys.get(f"{provider}_latency_ms_count", 0)
    total = keys.get(f"{provider}_latency_ms_sum", 0)
    return (total / count) if count else 0.0

print("|".join([
    str(keys["google_places"]),
    str(keys["serper"]),
    str(keys["hunter"]),
    str(keys["google_places_calls"]),
    str(keys["serper_calls"]),
    str(keys["hunter_calls"]),
    str(keys["google_places_success"]),
    str(keys["serper_success"]),
    str(keys["hunter_success"]),
    str(keys["google_places_error"]),
    str(keys["serper_error"]),
    str(keys["hunter_error"]),
    str(keys["google_places_cache_hit"]),
    str(keys["google_places_text_search_calls"]),
    str(keys["google_places_details_calls"]),
    str(keys["serper_cache_hit"]),
    str(keys["hunter_cache_hit"]),
    f"{avg_latency('google_places'):.1f}",
    f"{avg_latency('serper'):.1f}",
    f"{avg_latency('hunter'):.1f}",
    str(api_calls_total),
    str(api_success_total),
    str(api_error_total),
    str(cache_hits_total),
    f"{api_success_rate:.2f}",
    f"{cache_hit_rate:.2f}",
    f"{emails_per_api_call:.3f}",
    f"{google_cost_estimated_run:.4f}",
    f"{google_cost_estimated_mtd:.4f}",
    f"{google_cost_estimated_monthly_projected:.2f}",
    f"{emails_per_google_dollar:.3f}",
]))
END
)

IFS='|' read -r \
  api_google_places_count api_serper_count api_hunter_count \
  api_google_places_calls api_serper_calls api_hunter_calls \
  api_google_places_success api_serper_success api_hunter_success \
  api_google_places_error api_serper_error api_hunter_error \
  api_google_places_cache_hit api_google_places_text_search_calls api_google_places_details_calls api_serper_cache_hit api_hunter_cache_hit \
  api_google_places_avg_latency_ms api_serper_avg_latency_ms api_hunter_avg_latency_ms \
  api_calls_total api_success_total api_error_total api_cache_hits_total \
  api_success_rate cache_hit_rate emails_per_api_call \
  google_cost_estimated_run google_cost_estimated_mtd google_cost_estimated_monthly_projected emails_per_google_dollar <<< "$metrics_snapshot"

KPI_CSV="$LOG_DIR/daily_kpi.csv"
if [[ -f "$KPI_CSV" ]]; then
  existing_header="$(head -n 1 "$KPI_CSV")"
  if [[ "$existing_header" != *"google_cost_estimated_mtd"* ]]; then
    mv "$KPI_CSV" "$KPI_CSV.pre_metrics_${RUN_ID}.bak"
  fi
fi
if [[ ! -f "$KPI_CSV" ]]; then
  echo "date,timestamp,run_id,dry_run,pairs_selected,pairs_processed,daily_target,sent_in_run,replies_in_run,hard_bounces_in_run,soft_bounces_in_run,total_lead_files,sent_today_total,remaining_quota_end,pending_queue_end,run_duration_sec,discovery_duration_sec,enrich_duration_sec,outreach_duration_sec,api_calls_total,api_success_total,api_error_total,api_success_rate,cache_hits_total,cache_hit_rate,emails_per_api_call,google_places_calls,google_places_text_search_calls,google_places_details_calls,serper_calls,hunter_calls,google_places_avg_latency_ms,serper_avg_latency_ms,hunter_avg_latency_ms,google_cost_estimated_run,google_cost_estimated_mtd,google_cost_estimated_monthly_projected,emails_per_google_dollar" > "$KPI_CSV"
fi
echo "$(date +%Y-%m-%d),$(date '+%Y-%m-%d %H:%M:%S'),$RUN_ID,$DRY_RUN,$TOTAL,$COUNT,$DAILY_EMAIL_TARGET,${sent_count:-0},${reply_count:-0},${hard_bounce_count:-0},${soft_bounce_count:-0},$lead_count,$sent_today_end,$remaining_quota_end,$pending_queue_size_end,$RUN_DURATION_SEC,$DISCOVERY_DURATION_SEC,$ENRICH_DURATION_SEC,$OUTREACH_DURATION_SEC,${api_calls_total:-0},${api_success_total:-0},${api_error_total:-0},${api_success_rate:-0},${api_cache_hits_total:-0},${cache_hit_rate:-0},${emails_per_api_call:-0},${api_google_places_calls:-0},${api_google_places_text_search_calls:-0},${api_google_places_details_calls:-0},${api_serper_calls:-0},${api_hunter_calls:-0},${api_google_places_avg_latency_ms:-0},${api_serper_avg_latency_ms:-0},${api_hunter_avg_latency_ms:-0},${google_cost_estimated_run:-0},${google_cost_estimated_mtd:-0},${google_cost_estimated_monthly_projected:-0},${emails_per_google_dollar:-0}" >> "$KPI_CSV"
log "[KPI] Appended daily KPI row -> $KPI_CSV" | tee -a "$LOG_DIR/summary.log"

if [[ -f "$RUN_HISTORY_CSV" ]]; then
  history_header="$(head -n 1 "$RUN_HISTORY_CSV")"
  if [[ "$history_header" != *"google_cost_estimated_mtd"* ]]; then
    mv "$RUN_HISTORY_CSV" "$RUN_HISTORY_CSV.pre_google_cost_${RUN_ID}.bak"
  fi
fi
if [[ ! -f "$RUN_HISTORY_CSV" ]]; then
  echo "date,timestamp,run_id,dry_run,pairs_selected,pairs_processed,sent_in_run,replies_in_run,hard_bounces_in_run,soft_bounces_in_run,pending_queue_end,run_duration_sec,api_calls_total,api_success_rate,cache_hit_rate,emails_per_api_call,google_places_calls,google_places_text_search_calls,google_places_details_calls,serper_calls,hunter_calls,google_places_avg_latency_ms,serper_avg_latency_ms,hunter_avg_latency_ms,google_cost_estimated_run,google_cost_estimated_mtd,google_cost_estimated_monthly_projected,emails_per_google_dollar" > "$RUN_HISTORY_CSV"
fi
echo "$(date +%Y-%m-%d),$(date '+%Y-%m-%d %H:%M:%S'),$RUN_ID,$DRY_RUN,$TOTAL,$COUNT,${sent_count:-0},${reply_count:-0},${hard_bounce_count:-0},${soft_bounce_count:-0},$pending_queue_size_end,$RUN_DURATION_SEC,${api_calls_total:-0},${api_success_rate:-0},${cache_hit_rate:-0},${emails_per_api_call:-0},${api_google_places_calls:-0},${api_google_places_text_search_calls:-0},${api_google_places_details_calls:-0},${api_serper_calls:-0},${api_hunter_calls:-0},${api_google_places_avg_latency_ms:-0},${api_serper_avg_latency_ms:-0},${api_hunter_avg_latency_ms:-0},${google_cost_estimated_run:-0},${google_cost_estimated_mtd:-0},${google_cost_estimated_monthly_projected:-0},${emails_per_google_dollar:-0}" >> "$RUN_HISTORY_CSV"
log "[KPI] Appended run metrics history row -> $RUN_HISTORY_CSV" | tee -a "$LOG_DIR/summary.log"

success_alert=$(awk -v success="$api_success_rate" -v threshold="$API_SUCCESS_RATE_ALERT_THRESHOLD" 'BEGIN {print ((success + 0.0) < (threshold + 0.0)) ? 1 : 0}')
efficiency_alert=0
if (( ${api_calls_total:-0} > 0 )); then
  efficiency_alert=$(awk -v ratio="$emails_per_api_call" -v threshold="$EFFICIENCY_MIN_EMAILS_PER_API_CALL" 'BEGIN {print ((ratio + 0.0) < (threshold + 0.0)) ? 1 : 0}')
fi
projected_cost_alert=0
if awk -v threshold="$GOOGLE_MONTHLY_PROJECTED_COST_ALERT_THRESHOLD" 'BEGIN {exit !((threshold + 0.0) > 0)}'; then
  projected_cost_alert=$(awk -v projected="$google_cost_estimated_monthly_projected" -v threshold="$GOOGLE_MONTHLY_PROJECTED_COST_ALERT_THRESHOLD" 'BEGIN {print ((projected + 0.0) > (threshold + 0.0)) ? 1 : 0}')
fi

ALERTS_TEXT="No threshold alerts triggered."
if [[ "$success_alert" == "1" || "$efficiency_alert" == "1" || "$projected_cost_alert" == "1" || "${hard_bounce_count:-0}" -gt 0 ]]; then
  ALERTS_TEXT=""
  if [[ "$success_alert" == "1" ]]; then
    ALERTS_TEXT+="- API success rate below threshold (${api_success_rate}% < ${API_SUCCESS_RATE_ALERT_THRESHOLD}%)\n"
  fi
  if [[ "$efficiency_alert" == "1" ]]; then
    ALERTS_TEXT+="- Emails per API call below threshold (${emails_per_api_call} < ${EFFICIENCY_MIN_EMAILS_PER_API_CALL})\n"
  fi
  if [[ "$projected_cost_alert" == "1" ]]; then
    ALERTS_TEXT+="- Projected month-end Google cost above threshold ($${google_cost_estimated_monthly_projected} > $${GOOGLE_MONTHLY_PROJECTED_COST_ALERT_THRESHOLD})\n"
  fi
  if [[ "${hard_bounce_count:-0}" -gt 0 ]]; then
    ALERTS_TEXT+="- Hard bounces detected: ${hard_bounce_count}\n"
  fi
fi
ALERTS_TEXT_RENDERED="$(printf "%b" "$ALERTS_TEXT")"

API_SUMMARY=$(cat <<EOF
API Calls This Run:
- Google Places: ${api_google_places_count:-0} (calls=${api_google_places_calls:-0}, success=${api_google_places_success:-0}, error=${api_google_places_error:-0}, cache_hit=${api_google_places_cache_hit:-0}, avg_latency_ms=${api_google_places_avg_latency_ms:-0})
  - Text Search calls: ${api_google_places_text_search_calls:-0}
  - Place Details calls: ${api_google_places_details_calls:-0}
- Serper: ${api_serper_count:-0} (calls=${api_serper_calls:-0}, success=${api_serper_success:-0}, error=${api_serper_error:-0}, cache_hit=${api_serper_cache_hit:-0}, avg_latency_ms=${api_serper_avg_latency_ms:-0})
- Hunter: ${api_hunter_count:-0} (calls=${api_hunter_calls:-0}, success=${api_hunter_success:-0}, error=${api_hunter_error:-0}, cache_hit=${api_hunter_cache_hit:-0}, avg_latency_ms=${api_hunter_avg_latency_ms:-0})

Derived Efficiency:
- API calls total: ${api_calls_total:-0}
- API success rate: ${api_success_rate:-0}%
- Cache hit rate: ${cache_hit_rate:-0}%
- Emails/API call: ${emails_per_api_call:-0}
- Est. Google billed incremental run cost (tiered): \$${google_cost_estimated_run:-0}
- Est. Google billed MTD cost (tiered): \$${google_cost_estimated_mtd:-0}
- Est. Google projected month-end billed cost: \$${google_cost_estimated_monthly_projected:-0}
- Emails per Google dollar: ${emails_per_google_dollar:-0}
EOF
)

SUMMARY=$(cat <<EOF
Daily Pipeline Summary – $(date '+%A, %B %d, %Y')

Pairs Processed: $TOTAL
Leads Generated: $lead_count
Emails Sent: ${sent_count:-0}
Replies Detected: ${reply_count:-0}
Hard Bounces: ${hard_bounce_count:-0}
Soft Bounces: ${soft_bounce_count:-0}
Pending Queue End: ${pending_queue_size_end}

Durations:
- Run: ${RUN_DURATION_SEC}s
- Discovery: ${DISCOVERY_DURATION_SEC}s
- Enrichment: ${ENRICH_DURATION_SEC}s
- Outreach: ${OUTREACH_DURATION_SEC}s

$API_SUMMARY

Alerts:
$ALERTS_TEXT_RENDERED

Log files:
- Summary: $LOG_DIR/summary.log
- Email: $LOG_DIR/email.log
- KPI: $KPI_CSV
- Metrics history: $RUN_HISTORY_CSV
- Send audit JSON: ${SEND_AUDIT_JSON:-n/a}
- Send audit CSV: ${SEND_AUDIT_CSV:-n/a}
EOF
)

log "Sending Summary Email..." | tee -a "$LOG_DIR/summary.log"
if [[ "$DRY_RUN" == "true" ]]; then
  log "[DRY] Skipping summary email send." | tee -a "$LOG_DIR/summary.log"
else
if "$PYTHON_BIN" - <<END
import os, smtplib, ssl, time
from email.mime.text import MIMEText

try:
    import certifi
except Exception:
    certifi = None

sender=os.getenv("DAILY_LEAD_EMAIL_SENDER")
password=os.getenv("DAILY_LEAD_EMAIL_PASS")
receiver=os.getenv("REPLY_NOTIFY_TO", sender)
if sender and password:
    msg=MIMEText("""$SUMMARY""","plain","utf-8")
    msg["Subject"]="[ZBA Digital] Daily Pipeline Summary"
    msg["From"]=sender
    msg["To"]=receiver
    if certifi is not None:
        ctx=ssl.create_default_context(cafile=certifi.where())
    else:
        ctx=ssl.create_default_context()
    last_exc = None
    for attempt in range(3):
      try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ctx) as s:
          s.login(sender,password)
          s.sendmail(sender,[receiver],msg.as_string())
        last_exc = None
        break
      except Exception as exc:
        last_exc = exc
        print(f"[ERROR] SMTP summary send failed attempt {attempt + 1}/3: {exc}")
        if attempt < 2:
          time.sleep(3 ** attempt)
    if last_exc is not None:
      raise last_exc
END
  then
    log "Summary Email Sent to $REPLY_NOTIFY_TO" | tee -a "$LOG_DIR/summary.log"
  else
    log "[WARN] Summary Email failed to send." | tee -a "$LOG_DIR/summary.log"
  fi
  fi
log "Completed $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_DIR/summary.log"