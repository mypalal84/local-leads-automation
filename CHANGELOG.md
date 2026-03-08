# Changelog

## 2026-03-07

### Added

- Granular API telemetry for discovery and enrichment:
  - Calls, success/error counts, cache hits, and latency aggregates.
  - Split Google Places usage into Text Search vs Place Details counters.
- Pipeline stage timing metrics:
  - Run total, discovery, enrichment, and outreach durations.
- Expanded KPI output in `logs/daily_kpi.csv` with operational and efficiency metrics.
- Run metrics history log in `logs/run_metrics/history.csv` for trend tracking.
- Tiered Google billing estimator based on month-to-date split usage:
  - Incremental run billed cost.
  - Month-to-date billed cost.
  - Projected month-end billed cost.
  - Emails per Google dollar.
- Configurable alert thresholds:
  - `API_SUCCESS_RATE_ALERT_THRESHOLD`
  - `EFFICIENCY_MIN_EMAILS_PER_API_CALL`
  - `GOOGLE_MONTHLY_PROJECTED_COST_ALERT_THRESHOLD`
- New pricing controls:
  - `GOOGLE_TEXT_SEARCH_ENTERPRISE_PRICE_PER_1000`
  - `GOOGLE_PLACE_DETAILS_ENTERPRISE_PRICE_PER_1000`

### Changed

- Summary email now includes API efficiency and Google cost estimates.
- Alert section now flags projected monthly Google spend threshold breaches.
- README updated with monitoring and cost configuration variables.

### Notes

- Cost estimates are computed from pipeline usage logs and configured tier rates.
- Existing KPI/history files auto-migrate by backing up older schema files and writing new headers.
