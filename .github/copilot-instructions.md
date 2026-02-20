# Daily Leads - AI Agent Instructions

## Project Purpose
Lead generation system for local service businesses without websites. Uses Google Places API to find small businesses, enriches contact info via Serper→SerpAPI→Hunter.io cascade, and generates daily CSV reports.

## Two Script Variants

### 1. `lead_generator_free_mode.py` (Root)
- **Free tier focus**: 5,000 calls/month hard cap with auto-reset tracking
- **Usage tracking**: `cache/usage_log.json` tracks monthly API usage
- **Caching**: 7-day cache expiration in `cache/places_*.json`
- **Email enrichment**: DuckDuckGo scraping + pattern fallback (no paid APIs)
- **Limits**: 50 leads/day, 5 sample towns
- **Location**: Project root (legacy compatibility)

### 2. `src/lead_generator_no_website_enriched.py` (Production)
- **Multi-tier enrichment**: Serper (primary) → SerpAPI (403 fallback) → Hunter.io → Pattern
- **Website filtering**: Excludes businesses with websites via `get_place_details()`
- **Social media detection**: `is_social()` filters Facebook/Instagram/LinkedIn as "no website"
- **History tracking**: `data/lead_history.csv` prevents duplicate leads across runs
- **Email delivery**: Gmail SMTP with CSV attachment
- **Limits**: 50 leads/day, 10 towns
- **Location**: `src/` directory (current production)

## Key Architecture Patterns

### API Cascade Strategy
```python
# Enrichment waterfall with provider-specific error handling
def enrich_email(name, town):
    # Serper first (403 = API key revoked, break chain)
    if SERPER_API_KEY and r.status_code != 403:
        # Continue trying queries
    # SerpAPI second (backup search)
    if SERPAPI_API_KEY:
        # Same pattern matching
    # Hunter.io third (domain search by company name)
    if HUNTER_API_KEY:
        # Company lookup, not domain
    # Pattern Generator last (always succeeds with fallback)
    return "info@{town}.com, contact@{town}.com", "Pattern Generator"
```
**Critical**: 403 from Serper immediately breaks to SerpAPI (indicates revoked key, not rate limit)

### Cache Architecture
- **Cache keys**: Sanitized query strings via `re.sub(r'[^a-zA-Z0-9_]', '_', query)`
- **TTL**: 7 days (`time.time() - os.path.getmtime(fn) < 7 * 86400`)
- **Bypass logic**: When monthly quota exceeded, cache becomes read-only fallback
- **No cache invalidation**: Stale data persists full 7 days (business trade-off for API savings)

### Data Structures
```python
# Standard place normalization across both scripts
normalize_place(p, service):
    return {
        "name/business": p.get("name"),
        "address": p.get("formatted_address") or p.get("vicinity"),
        "place_id": p.get("place_id"),
        "rating": p.get("rating"),
        "service": service  # Injected from search query
    }
```

## Environment Setup

### Required API Keys
```bash
GOOGLE_PLACES_API_KEY=xxx        # Text Search + Place Details
SERPER_API_KEY=xxx               # Primary email search
SERPAPI_API_KEY=xxx              # Backup search (403 fallback)
HUNTER_API_KEY=xxx               # Company email finder
DAILY_LEAD_EMAIL_SENDER=xxx      # Gmail address
DAILY_LEAD_EMAIL_PASS=xxx        # Gmail App Password (not account password)
DAILY_LEAD_EMAIL_TO=xxx          # Report recipient
```

### Execution Methods
```bash
# Manual runs (development)
python3 src/lead_generator_no_website_enriched.py

# Automated runs (production)
bash scripts/run_leads.sh  # Loads .env, redirects to logs/

# Python path in run_leads.sh is HARDCODED:
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
```

## Critical Workflows

### Adding New Services
Edit `SERVICES` list in either script:
```python
# lead_generator_free_mode.py: Line ~108
SERVICES = ["plumber","roofer","electrician","hvac","cleaning service"]

# lead_generator_no_website_enriched.py: Lines 30-35
SERVICES = [
    "plumber","roofer","electrician","contractor","landscaper","hvac",
    "dog walker","dentist","chiropractor","pest control","cleaning service",
    ...
]
```
Services become part of Place API query: `"{service} {town}, {state}"`

### Monthly Usage Reset
Free mode auto-resets when `usage_log.json` month != current month:
```python
if last.year != now.year or last.month != now.month:
    dat = {"count":0, "month": now.strftime("%Y-%m-%d")}
```
**Manual reset**: Delete `cache/usage_log.json`

### Lead History Deduplication
`update_history()` merges new leads with existing via:
```python
all_df = pd.concat([old, df]).drop_duplicates(subset=["Business","Phone","Email (Enriched)"])
```
**Key**: Uses exact string match on ALL three columns (not place_id)

## File Structure Logic

### Data Directories
- `data/towns_1000.csv`: Source truth for U.S. cities (SimpleMaps API, sorted by population)
- `data/lead_history.csv`: Persistent deduplication store across runs
- `cache/*.json`: Places API responses + email enrichment results
- `logs/`: Stdout/stderr from `run_leads.sh` (daily_run.log, daily_run_error.log)

### Output Files
Pattern: `no_website_{variant}_{YYYY-MM-DD}.csv`
- Free mode: `no_website_free_2026-02-20.csv`
- Enriched: `no_website_v5_2026-02-20.csv`

## Common Pitfalls

1. **API quota exhaustion**: Free mode stops at 5000 calls. Check `cache/usage_log.json` count
2. **Gmail App Passwords**: Regular passwords fail SMTP. Must generate App Password in Google Account settings
3. **Hardcoded Python path**: `scripts/run_leads.sh` breaks if Python install location changes
4. **Social media as websites**: Script excludes Facebook/Instagram pages (by design)
5. **Email pattern accuracy**: Pattern Generator is last resort, creates unverified addresses

## Testing Approach
- **No formal test suite**: Manual CSV inspection workflow
- **Email verification**: Real SMTP send in production (no dry-run mode)
- **API mocking**: Use cache files for offline testing
- **Debug output**: Emoji-prefixed print statements (✅ success, ⚠️ warnings, 🚫 errors)

## Dependencies
See [requirements.txt](requirements.txt):
- `pandas==3.0.0`: CSV operations, sampling, deduplication
- `requests==2.32.5`: All HTTP operations (no async)
- `beautifulsoup4`: DuckDuckGo HTML parsing (free mode only)
- Built-in: `smtplib`, `email`, `datetime`, `json`, `re`

## Future Enhancements (Not Implemented)
- Async API calls for faster enrichment
- Webhook delivery vs email
- Rate limit backoff strategies
- Database storage vs CSV
