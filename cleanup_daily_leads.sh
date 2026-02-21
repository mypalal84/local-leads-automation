#!/bin/bash
# ===========================================================
#  Cleanup script for Daily_Leads automation (Feb 2026)
#  Safely removes temp/cache files & zips CSV backups
# ===========================================================

BASE_DIR="$HOME/Scripts/Daily_Leads"
BACKUP_DIR="$BASE_DIR/backups"

echo "🧹  Cleaning up Daily_Leads in: $BASE_DIR"
cd "$BASE_DIR" || { echo "Folder not found!"; exit 1; }

# ---- Create a backups folder if missing ----
mkdir -p "$BACKUP_DIR"

# ---- Backup all CSV exports ----
echo "💾  Archiving CSV files before cleanup..."
cd "$BASE_DIR/src" || exit 1
ts=$(date +"%Y-%m-%d_%H-%M-%S")
zip -rq "$BACKUP_DIR/csv_backup_$ts.zip" daily_enriched_leads_*.csv 2>/dev/null
echo "✅  Saved archive: $BACKUP_DIR/csv_backup_$ts.zip"

# ---- Delete cache JSONs and usage logs ----
echo "🗑  Removing cached Google Places data..."
rm -rf "$BASE_DIR/cache"/*.json 2>/dev/null
rm -f "$BASE_DIR/cache/usage_log.json" 2>/dev/null

# ---- Remove redundant or prototype scripts ----
echo "🗑  Removing redundant scripts from src ..."
rm -f \
  "$BASE_DIR/src/lead_generator_no_website_enriched.py" \
  "$BASE_DIR/src/lead_generator_optimized.py" \
  "$BASE_DIR/src/lead_generator_free_mode.py" \
  "$BASE_DIR/src/folder_list.txt" \
  "$BASE_DIR/src/no_website_v5_"*.csv 2>/dev/null

# ---- Delete logs and macOS metadata ----
echo "🗑  Cleaning logs and .DS_Store junk..."
rm -f "$BASE_DIR"/.DS_Store "$BASE_DIR/src/.DS_Store" "$BASE_DIR/data/.DS_Store"
rm -f "$BASE_DIR/daily_run.log" "$BASE_DIR/daily_run_error.log"
rm -f "$BASE_DIR/logs/daily_run.log" "$BASE_DIR/logs/daily_run_error.log"

# ---- Optional remove .git ----
if [ -d "$BASE_DIR/.git" ]; then
  read -p "Delete .git folder (remove version history)? [y/N] " RESP
  if [[ "$RESP" =~ ^[Yy]$ ]]; then
    rm -rf "$BASE_DIR/.git"
    echo "✅  Git repo removed."
  else
    echo "⏩  Skipping Git removal."
  fi
fi

# ---- Keep only 3 latest CSVs ----
echo "🧾  Pruning older CSVs (keeping newest 3)..."
ls -t daily_enriched_leads_*.csv 2>/dev/null | tail -n +4 | xargs -r rm --

echo "✨  Cleanup complete!"