#!/usr/bin/env python3
"""Generate post-run send audit lists from a daily sent ledger.

Outputs:
- JSON summary with three lists:
  - suppressed_hits
  - current_send
  - fail_without_suppression
- CSV detail rows for each email in the ledger with status and reason.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTREACH_DIR = os.path.join(SCRIPT_DIR, "outreach")
if OUTREACH_DIR not in sys.path:
    sys.path.insert(0, OUTREACH_DIR)

import send_cold_emails as sender


def normalize_email_list(value: str) -> List[str]:
    text = "" if pd.isna(value) else str(value)
    parts = [p.replace("\u202f", " ").strip().lower() for p in text.split(",") if p.strip()]
    return parts


def load_sent_rows(daily_sent_path: str) -> List[List[str]]:
    with open(daily_sent_path, newline="", encoding="utf-8") as f:
        return [row for row in csv.reader(f) if row and len(row) >= 4]


def source_candidates(base_dir: str, source_file: str) -> List[str]:
    candidates = [
        os.path.join(base_dir, "data", "current", source_file),
        os.path.join(base_dir, "data", source_file),
    ]
    candidates.extend(glob.glob(os.path.join(base_dir, "data", "archive", "*", source_file)))
    unique_existing = sorted({path for path in candidates if os.path.exists(path)})
    return unique_existing


def find_row_for_email(
    base_dir: str,
    source_file: str,
    email_addr: str,
    source_cache: Dict[str, List[pd.DataFrame]],
) -> Optional[dict]:
    if source_file not in source_cache:
        frames: List[pd.DataFrame] = []
        for path in source_candidates(base_dir, source_file):
            try:
                frames.append(pd.read_csv(path))
            except Exception:
                continue
        source_cache[source_file] = frames

    target = (email_addr or "").strip().lower()
    for df in source_cache[source_file]:
        for _, row in df.iterrows():
            if target in normalize_email_list(row.get("emails", "")):
                return row.to_dict()
    return None


def evaluate_email(
    email_addr: str,
    row: Optional[dict],
    suppressed_set: set,
    include_suppression: bool,
) -> Tuple[bool, str]:
    email_addr = (email_addr or "").strip().lower()
    if row is None:
        return False, "missing_row"

    if include_suppression and email_addr in suppressed_set:
        return False, "suppressed"

    if sender.PRE_SEND_VALIDATE_EMAILS:
        ok, why = sender.should_send_to_email(email_addr)
        if not ok:
            return False, f"email_validation:{why}"

    skip_non_biz, why_non_biz = sender.should_skip_non_business_lead(row, email_addr)
    if skip_non_biz:
        return False, f"non_business:{why_non_biz}"

    skip_mismatch, why_mismatch = sender.should_skip_domain_mismatch(row, email_addr)
    if skip_mismatch:
        return False, f"domain_mismatch:{why_mismatch}"

    domain = email_addr.split("@", 1)[1] if "@" in email_addr else ""
    if (
        sender.PRE_SEND_WEBSITE_GUARD
        and domain
        and sender.should_apply_pre_send_website_guard(row, email_addr)
        and sender.has_live_business_website(domain)
    ):
        return False, "website_guard_live_domain"

    if sender.score_lead(row, email_addr) < sender.LEAD_SCORE_THRESHOLD:
        return False, "lead_score_below_threshold"

    return True, "send"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate post-run send audit lists.")
    parser.add_argument("--base-dir", required=True, help="Project base directory (Daily_Leads root).")
    parser.add_argument("--daily-sent", required=True, help="Path to daily_sent_<date>.csv ledger file.")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), help="Run ID suffix.")
    parser.add_argument("--output-dir", default="", help="Directory for generated audit files.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    base_dir = os.path.abspath(args.base_dir)
    daily_sent_path = os.path.abspath(args.daily_sent)
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else os.path.join(base_dir, "logs", "run_metrics")

    if not os.path.exists(daily_sent_path):
        print(f"[AUDIT] Daily sent ledger not found: {daily_sent_path}")
        return 1

    os.makedirs(output_dir, exist_ok=True)

    rows = load_sent_rows(daily_sent_path)
    suppressed = sender.load_suppression_list()
    source_cache: Dict[str, List[pd.DataFrame]] = {}

    suppressed_hits: List[str] = []
    current_send: List[str] = []
    fail_without_suppression: List[dict] = []
    reason_counts: Counter = Counter()
    detail_rows: List[dict] = []

    for rec in rows:
        email_addr = rec[0].strip().lower()
        source_file = rec[3].strip()
        row = find_row_for_email(base_dir, source_file, email_addr, source_cache)

        ok_current, reason_current = evaluate_email(email_addr, row, suppressed, include_suppression=True)
        ok_without, reason_without = evaluate_email(email_addr, row, suppressed, include_suppression=False)

        if reason_current == "suppressed":
            suppressed_hits.append(email_addr)
        if ok_current:
            current_send.append(email_addr)
        if not ok_without:
            fail_without_suppression.append({"email": email_addr, "reason": reason_without})

        if not ok_current:
            reason_counts[reason_current] += 1

        detail_rows.append(
            {
                "email": email_addr,
                "source_file": source_file,
                "status_current": "send" if ok_current else "skip",
                "reason_current": reason_current,
                "status_without_suppression": "send" if ok_without else "skip",
                "reason_without_suppression": reason_without,
                "name": "" if row is None else str(row.get("name", "")),
            }
        )

    summary = {
        "run_id": args.run_id,
        "daily_sent_path": daily_sent_path,
        "total_rows": len(rows),
        "counts": {
            "suppressed_hits": len(set(suppressed_hits)),
            "current_send": len(set(current_send)),
            "fail_without_suppression": len({item["email"] for item in fail_without_suppression}),
        },
        "suppressed_hits": sorted(set(suppressed_hits)),
        "current_send": sorted(set(current_send)),
        "fail_without_suppression": sorted(
            {tuple((item["email"], item["reason"])) for item in fail_without_suppression}
        ),
        "skip_reason_counts_current": dict(reason_counts),
    }

    json_path = os.path.join(output_dir, f"send_audit_{args.run_id}.json")
    csv_path = os.path.join(output_dir, f"send_audit_{args.run_id}.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "email",
                "source_file",
                "status_current",
                "reason_current",
                "status_without_suppression",
                "reason_without_suppression",
                "name",
            ],
        )
        writer.writeheader()
        writer.writerows(detail_rows)

    latest_json = os.path.join(output_dir, "send_audit_latest.json")
    latest_csv = os.path.join(output_dir, "send_audit_latest.csv")
    for src, dst in ((json_path, latest_json), (csv_path, latest_csv)):
        try:
            if os.path.exists(dst):
                os.remove(dst)
            os.symlink(src, dst)
        except Exception:
            # Fallback for filesystems that do not permit symlinks.
            if src.endswith(".json"):
                with open(src, "r", encoding="utf-8") as fsrc, open(dst, "w", encoding="utf-8") as fdst:
                    fdst.write(fsrc.read())
            else:
                with open(src, "r", encoding="utf-8") as fsrc, open(dst, "w", encoding="utf-8") as fdst:
                    fdst.write(fsrc.read())

    print(
        "[AUDIT] Generated "
        f"{json_path} and {csv_path} | "
        f"suppressed={summary['counts']['suppressed_hits']} "
        f"current_send={summary['counts']['current_send']} "
        f"fail_without_suppression={summary['counts']['fail_without_suppression']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
