#!/usr/bin/env python3
"""Quick post-run health check for Daily_Leads.

Usage:
  /Users/alexcahn/Scripts/.venv/bin/python src/health_check.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_CSV = ROOT / "logs" / "run_metrics" / "history.csv"
OUTCOMES_CSV = ROOT / "logs" / "run_metrics" / "pair_outcomes.csv"

TARGET_EPA = 0.05
TARGET_SENT = 12
TARGET_API_MAX = 220
LOOKBACK_RUNS = 5


def load_history_rows() -> list[dict]:
    if not HISTORY_CSV.exists():
        return []
    rows: list[dict] = []
    with HISTORY_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dry = str((row or {}).get("dry_run", "")).strip().lower()
            if dry in {"true", "1", "yes"}:
                continue
            rows.append(row)
    return rows


def as_int(row: dict, key: str) -> int:
    try:
        return int(float(row.get(key, 0) or 0))
    except Exception:
        return 0


def as_float(row: dict, key: str) -> float:
    try:
        return float(row.get(key, 0) or 0)
    except Exception:
        return 0.0


def load_zero_no_output_for_run(run_id: str) -> tuple[int, int]:
    if not OUTCOMES_CSV.exists() or not run_id:
        return 0, 0
    zero_sent = 0
    no_output = 0
    with OUTCOMES_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("run_id") or "").strip() != run_id:
                continue
            sent_delta = as_int(row, "sent_delta")
            no_out = as_int(row, "no_output")
            if sent_delta <= 0:
                zero_sent += 1
            if no_out > 0:
                no_output += 1
    return zero_sent, no_output


def fmt_status(ok: bool) -> str:
    return "OK" if ok else "MISS"


def main() -> int:
    rows = load_history_rows()
    if not rows:
        print("No non-dry runs found in logs/run_metrics/history.csv")
        return 0

    latest = rows[-1]
    lookback = rows[-(LOOKBACK_RUNS + 1):-1] if len(rows) > 1 else []

    run_id = (latest.get("run_id") or "").strip()
    sent = as_int(latest, "sent_in_run")
    api = as_int(latest, "api_calls_total")
    epa = as_float(latest, "emails_per_api_call")
    pairs = as_int(latest, "pairs_processed")
    zero_sent_pairs, no_output_pairs = load_zero_no_output_for_run(run_id)

    print(f"Latest run: {latest.get('timestamp', '')} ({run_id})")
    print(f"- Sent: {sent} [{fmt_status(sent >= TARGET_SENT)} target>={TARGET_SENT}]")
    print(f"- API calls: {api} [{fmt_status(api <= TARGET_API_MAX)} target<={TARGET_API_MAX}]")
    print(f"- Emails/API: {epa:.3f} [{fmt_status(epa >= TARGET_EPA)} target>={TARGET_EPA:.3f}]")
    print(f"- Pairs processed: {pairs}")
    print(f"- Zero-send pairs: {zero_sent_pairs}")
    print(f"- No-output events: {no_output_pairs}")

    if lookback:
        avg_sent = sum(as_int(r, "sent_in_run") for r in lookback) / len(lookback)
        avg_api = sum(as_int(r, "api_calls_total") for r in lookback) / len(lookback)
        avg_epa = sum(as_float(r, "emails_per_api_call") for r in lookback) / len(lookback)
        print("Recent baseline (previous runs):")
        print(f"- Avg sent: {avg_sent:.2f}")
        print(f"- Avg API calls: {avg_api:.1f}")
        print(f"- Avg emails/API: {avg_epa:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
