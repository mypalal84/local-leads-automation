#!/usr/bin/env python3
"""Aggregate daily pipeline metrics from logs into metrics.csv.

Parses:
- logs/summary.log for pairs processed, leads generated, emails sent
- logs/email.log for replies detected (because summary.log does not emit reply lines)

Output CSV schema:
  date,pairs_processed,leads_generated,emails_sent,replies_detected
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path

TIMESTAMP_DATE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\s")
PAIR_RE = re.compile(r"---\s*\[\s*\d+\s*/\s*\d+\s*\]")
LEADS_RE = re.compile(r"Leads discovered:\s*(\d+)")
SENT_DELTA_RE = re.compile(r"\[PAIR-RESULT\]\s+sent_delta=(\d+)")
REPLY_RE = re.compile(r"\[REPLY\]")

CSV_COLUMNS = [
    "date",
    "pairs_processed",
    "leads_generated",
    "emails_sent",
    "replies_detected",
]


def _iter_lines(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            yield raw.rstrip("\n")


def _collect_from_summary(summary_log: Path, target_date: str) -> tuple[int, int, int]:
    active_date: str | None = None
    pairs_processed = 0
    leads_generated = 0
    emails_sent = 0

    for line in _iter_lines(summary_log) or ():
        m_date = TIMESTAMP_DATE_RE.match(line)
        if m_date:
            active_date = m_date.group(1)

        if active_date != target_date:
            continue

        if PAIR_RE.search(line):
            pairs_processed += 1

        m_leads = LEADS_RE.search(line)
        if m_leads:
            leads_generated += int(m_leads.group(1))

        m_sent = SENT_DELTA_RE.search(line)
        if m_sent:
            emails_sent += int(m_sent.group(1))

    return pairs_processed, leads_generated, emails_sent


def _collect_replies(email_log: Path, target_date: str) -> int:
    active_date: str | None = None
    replies_detected = 0

    for line in _iter_lines(email_log) or ():
        m_date = TIMESTAMP_DATE_RE.match(line)
        if m_date:
            active_date = m_date.group(1)

        if active_date != target_date:
            continue

        if REPLY_RE.search(line):
            replies_detected += 1

    return replies_detected


def _upsert_metrics_row(metrics_csv: Path, row: dict[str, str]) -> None:
    rows: list[dict[str, str]] = []

    if metrics_csv.exists():
        with metrics_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for existing in reader:
                # Keep only known columns and default missing values to "0".
                cleaned = {col: existing.get(col, "0") for col in CSV_COLUMNS}
                rows.append(cleaned)

    replaced = False
    for idx, existing in enumerate(rows):
        if existing.get("date") == row["date"]:
            rows[idx] = row
            replaced = True
            break

    if not replaced:
        rows.append(row)

    rows.sort(key=lambda r: r.get("date", ""))

    with metrics_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append daily metrics snapshot from logs.")
    parser.add_argument(
        "--summary-log",
        default="logs/summary.log",
        help="Path to summary.log (default: logs/summary.log)",
    )
    parser.add_argument(
        "--email-log",
        default="logs/email.log",
        help="Path to email.log for reply counts (default: logs/email.log)",
    )
    parser.add_argument(
        "--metrics-csv",
        default="metrics.csv",
        help="Path to output metrics CSV (default: metrics.csv)",
    )
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        dt.date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit(f"Invalid --date value: {args.date}. Use YYYY-MM-DD.")

    summary_log = Path(args.summary_log)
    email_log = Path(args.email_log)
    metrics_csv = Path(args.metrics_csv)

    pairs_processed, leads_generated, emails_sent = _collect_from_summary(summary_log, args.date)
    replies_detected = _collect_replies(email_log, args.date)

    row = {
        "date": args.date,
        "pairs_processed": str(pairs_processed),
        "leads_generated": str(leads_generated),
        "emails_sent": str(emails_sent),
        "replies_detected": str(replies_detected),
    }

    _upsert_metrics_row(metrics_csv, row)

    print(
        f"Updated {metrics_csv} for {args.date}: "
        f"pairs={pairs_processed}, leads={leads_generated}, sent={emails_sent}, replies={replies_detected}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
