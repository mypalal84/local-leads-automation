# Daily Leads - AI Agent Instructions

## Current Project Scope
This repo runs a local daily lead pipeline for businesses without websites:

1. Discover leads (`discover_no_website_leads.py`)
2. Enrich emails (`find_no_website_emails.py`)
3. Send outreach + process replies (`send_cold_emails.py`)
4. Orchestrate all steps (`master_daily_pipeline.sh`)

Prefer this modern pipeline. Legacy scripts in `archive/` are not the source of truth.

## Canonical Entry Point
- Main runtime entry: `src/master_daily_pipeline.sh`
- Cron should call this script.
- The script sources `.env`, selects city/service pairs, runs discovery/enrichment/sending, and writes run metrics.

## Source-of-Truth Files
- `src/discover_no_website_leads.py`
- `src/find_no_website_emails.py`
- `src/send_cold_emails.py`
- `src/master_daily_pipeline.sh`
- `README.md` (operational behavior + env documentation)

When updating behavior, keep README and tests aligned.

## Key Data/Log Paths (Current)

### Data
- `data/leads_<city>_<service>_NO_WEBSITE_<date>.csv`
- `data/daily_sent/daily_sent_<date>.csv` (daily send cap ledger)
- `data/pending_leads.csv` (deferred queue)
- `data/sent_log.csv` (global already-contacted ledger)
- `data/replies.csv`
- `data/suppressions.csv`
- `data/cache/` (Serper/Hunter/Places caches)
- `data/archive/` (archived lead/enrichment CSVs)

### Logs
- `logs/summary.log`
- `logs/email.log`
- `logs/pipeline.log`
- `logs/daily_kpi.csv`
- `logs/run_metrics/run_metrics_<timestamp>.json`
- `logs/archive/<timestamp>/run_metrics_*.json`

## Discovery Behavior (Google Places)
- Default provider is `google_places` when `GOOGLE_PLACES_API_KEY` exists.
- Fallback provider is `serper`.
- Important controls:
  - `GOOGLE_DISCOVERY_SEARCH_CALLS`
  - `GOOGLE_DISCOVERY_TARGET_LEADS`
  - `GOOGLE_DETAILS_FALLBACK_LIMIT`
- Discovery should minimize paid API calls while preserving enough no-website leads.

## Sender + Queue Behavior
- Pending-first flow: `send_cold_emails.py` consumes `data/pending_leads.csv` before fresh leads.
- Daily cap enforcement uses `data/daily_sent/daily_sent_<date>.csv`.
- Domain throttling and suppression list checks run before send.
- Reply handling updates suppressions and reply logs.

## Archive/Retention Behavior
- `master_daily_pipeline.sh` archives prior run-metrics into `logs/archive/<run_id>/`.
- Old archive folders are pruned by `LOG_ARCHIVE_RETENTION_DAYS` (default 60).
- `0` disables pruning.

## Environment Variables to Respect

### Throughput / scheduling
- `DAILY_EMAIL_TARGET`
- `EXPECTED_SENDS_PER_PAIR`
- `MAX_PAIRS_PER_RUN`
- `ENRICH_BUFFER_MULTIPLIER`
- `PIPELINE_DELAY_BETWEEN_RUNS`
- `DRY_RUN`

### Quality / sending policy
- `LEAD_SCORE_THRESHOLD`
- `PRE_ENRICH_SCORE_FILTER`
- `MAX_EMAILS_PER_DOMAIN`
- `BLOCK_GENERIC_INBOXES`
- `SKIP_REPLY_CHECK_CLEANUP`

### Discovery / cost control
- `DISCOVERY_PROVIDER`
- `GOOGLE_DISCOVERY_SEARCH_CALLS`
- `GOOGLE_DISCOVERY_TARGET_LEADS`
- `GOOGLE_DETAILS_FALLBACK_LIMIT`
- `CACHE_TTL_DAYS`
- `LOG_ARCHIVE_RETENTION_DAYS`

## Testing Expectations
- Use pytest tests under `tests/`.
- Preferred targeted test runs during iteration:
  - `tests/test_discover_no_website_leads.py`
  - `tests/test_find_no_website_emails.py`
  - `tests/test_send_cold_emails.py`
- If coverage gating interferes with a focused run, use:
  - `python -m pytest -o addopts='' <test_file>`

## Development Guardrails
- Keep changes minimal and production-safe.
- Preserve backward compatibility for path migrations where practical.
- Do not reintroduce deprecated SerpAPI fallback logic unless explicitly requested.
- Keep logs/data layout consistent with README.
- Update tests and docs when changing behavior.
