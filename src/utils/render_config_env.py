#!/usr/bin/env python3
"""Render selected config.yaml values as shell `export` statements."""

from __future__ import annotations

import shlex

from config import get_config

KEY_MAP = {
    "DAILY_EMAIL_TARGET": "pipeline.daily_email_target",
    "EXPECTED_SENDS_PER_PAIR": "pipeline.expected_sends_per_pair",
    "MAX_PAIRS_PER_RUN": "pipeline.max_pairs_per_run",
    "ENRICH_BUFFER_MULTIPLIER": "pipeline.enrich_buffer_multiplier",
    "MAX_ENRICH_LEADS_PER_PAIR": "pipeline.max_enrich_leads_per_pair",
    "PIPELINE_DELAY_BETWEEN_RUNS": "pipeline.sleep_seconds",
    "ZERO_SEND_STREAK_STOP": "pipeline.zero_send_streak_stop",
    "GOOGLE_DISCOVERY_SEARCH_CALLS": "discovery.search_calls",
    "GOOGLE_DISCOVERY_TARGET_LEADS": "discovery.target_leads",
    "GOOGLE_DETAILS_FALLBACK_LIMIT": "discovery.details_fallback_limit",
    "PARALLEL_DISCOVERY_ENABLED": "discovery.parallel.enabled",
    "PARALLEL_DISCOVERY_MAX_JOBS": "discovery.parallel.max_jobs",
    "PARALLEL_DISCOVERY_STAGGER_SEC": "discovery.parallel.stagger_seconds",
    "LEAD_SCORE_THRESHOLD": "enrichment.lead_score_threshold",
    "PRE_ENRICH_SCORE_FILTER": "enrichment.pre_enrich_score_filter",
    "MAX_EMAILS_PER_DOMAIN": "outreach.max_emails_per_domain",
    "PRE_SEND_VALIDATE_EMAILS": "outreach.pre_send_validate_emails",
}


def shell_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def main() -> None:
    for env_name, key_path in KEY_MAP.items():
        value = get_config(key_path, default=None, env_var=None)
        if value is None:
            continue
        quoted = shlex.quote(shell_value(value))
        print(f"export {env_name}={quoted}")


if __name__ == "__main__":
    main()
