import os
import pathlib
import subprocess

import pytest


@pytest.mark.integration
def test_master_pipeline_dry_run_writes_kpi(tmp_path):
    brew_bash = pathlib.Path("/opt/homebrew/bin/bash")
    if not brew_bash.exists():
        pytest.skip("Requires Homebrew bash at /opt/homebrew/bin/bash")

    home = tmp_path / "home"
    base_dir = home / "Scripts" / "Daily_Leads"
    src_dir = base_dir / "src"
    logs_dir = base_dir / "logs"
    data_dir = base_dir / "data"

    src_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    project_root = pathlib.Path(__file__).resolve().parents[1]
    source_script = project_root / "src" / "pipeline" / "master_daily_pipeline.sh"
    target_script = src_dir / "master_daily_pipeline.sh"
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
    target_script.chmod(0o755)

    env_file = base_dir / ".env"
    env_file.write_text(
        "DAILY_LEAD_EMAIL_SENDER=test@example.com\n"
        "DAILY_LEAD_EMAIL_PASS=dummy\n"
        "REPLY_NOTIFY_TO=test@example.com\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DRY_RUN"] = "true"
    env["PIPELINE_DELAY_BETWEEN_RUNS"] = "0"
    env["DAILY_EMAIL_TARGET"] = "50"
    env["EXPECTED_SENDS_PER_PAIR"] = "5"
    env["MAX_PAIRS_PER_RUN"] = "10"

    subprocess.run([str(target_script)], check=True, env=env)

    kpi_path = logs_dir / "daily_kpi.csv"
    assert kpi_path.exists()

    rows = kpi_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) >= 2
    assert rows[0].startswith("date,timestamp,run_id,dry_run")
    assert ",true," in rows[-1]

    fields = rows[-1].split(",")
    pairs_selected = int(fields[4].strip())
    # target=50 and expected sends per pair=5 => 10 selected pairs.
    assert pairs_selected == 10

    summary_log = (logs_dir / "summary.log").read_text(encoding="utf-8")
    assert "[KPI] Appended daily KPI row" in summary_log


@pytest.mark.integration
def test_master_pipeline_respects_env_daily_target_for_pair_selection(tmp_path):
    brew_bash = pathlib.Path("/opt/homebrew/bin/bash")
    if not brew_bash.exists():
        pytest.skip("Requires Homebrew bash at /opt/homebrew/bin/bash")

    home = tmp_path / "home"
    base_dir = home / "Scripts" / "Daily_Leads"
    src_dir = base_dir / "src"
    logs_dir = base_dir / "logs"
    data_dir = base_dir / "data"

    src_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    project_root = pathlib.Path(__file__).resolve().parents[1]
    source_script = project_root / "src" / "pipeline" / "master_daily_pipeline.sh"
    target_script = src_dir / "master_daily_pipeline.sh"
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
    target_script.chmod(0o755)

    env_file = base_dir / ".env"
    env_file.write_text(
        "DAILY_LEAD_EMAIL_SENDER=test@example.com\n"
        "DAILY_LEAD_EMAIL_PASS=dummy\n"
        "REPLY_NOTIFY_TO=test@example.com\n"
        "DAILY_EMAIL_TARGET=7\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DRY_RUN"] = "true"
    env["PIPELINE_DELAY_BETWEEN_RUNS"] = "0"
    env["DAILY_EMAIL_TARGET"] = "7"
    env["EXPECTED_SENDS_PER_PAIR"] = "5"

    subprocess.run([str(target_script)], check=True, env=env)

    kpi_path = logs_dir / "daily_kpi.csv"
    assert kpi_path.exists()
    rows = kpi_path.read_text(encoding="utf-8").strip().splitlines()
    fields = rows[-1].split(",")
    pairs_selected = int(fields[4].strip())
    daily_target = int(fields[6].strip())

    assert daily_target == 7
    assert pairs_selected == 2


@pytest.mark.integration
def test_master_pipeline_adaptive_pair_scheduling_uses_history(tmp_path):
    brew_bash = pathlib.Path("/opt/homebrew/bin/bash")
    if not brew_bash.exists():
        pytest.skip("Requires Homebrew bash at /opt/homebrew/bin/bash")

    home = tmp_path / "home"
    base_dir = home / "Scripts" / "Daily_Leads"
    src_dir = base_dir / "src"
    logs_dir = base_dir / "logs"
    run_metrics_dir = logs_dir / "run_metrics"
    data_dir = base_dir / "data"

    src_dir.mkdir(parents=True)
    run_metrics_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    project_root = pathlib.Path(__file__).resolve().parents[1]
    source_script = project_root / "src" / "pipeline" / "master_daily_pipeline.sh"
    target_script = src_dir / "master_daily_pipeline.sh"
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
    target_script.chmod(0o755)

    env_file = base_dir / ".env"
    env_file.write_text(
        "DAILY_LEAD_EMAIL_SENDER=test@example.com\n"
        "DAILY_LEAD_EMAIL_PASS=dummy\n"
        "REPLY_NOTIFY_TO=test@example.com\n",
        encoding="utf-8",
    )

    # Low-yield history: 3 sends over 3 processed pairs => 1 expected send per pair.
    (run_metrics_dir / "history.csv").write_text(
        "date,timestamp,run_id,dry_run,pairs_selected,pairs_processed,sent_in_run,replies_in_run,hard_bounces_in_run,soft_bounces_in_run,pending_queue_end,run_duration_sec,api_calls_total,api_success_rate,cache_hit_rate,emails_per_api_call,google_places_calls,google_places_text_search_calls,google_places_details_calls,serper_calls,hunter_calls,google_places_avg_latency_ms,serper_avg_latency_ms,hunter_avg_latency_ms,google_cost_estimated_run,google_cost_estimated_mtd,google_cost_estimated_monthly_projected,emails_per_google_dollar\n"
        "2026-03-09,2026-03-09 07:00:00,2026-03-09_07-00-00,false,20,3,3,0,0,0,0,100,50,99.0,10.0,0.06,10,0,0,20,20,300,400,500,0,0,0,0\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DRY_RUN"] = "true"
    env["PIPELINE_DELAY_BETWEEN_RUNS"] = "0"
    env["DAILY_EMAIL_TARGET"] = "10"
    env["EXPECTED_SENDS_PER_PAIR"] = "5"
    env["MAX_PAIRS_PER_RUN"] = "10"
    env["ADAPTIVE_PAIR_SCHEDULING"] = "true"
    env["ADAPTIVE_LOOKBACK_RUNS"] = "3"
    env["ADAPTIVE_MIN_EXPECTED_SENDS_PER_PAIR"] = "1"
    env["ADAPTIVE_MAX_EXPECTED_SENDS_PER_PAIR"] = "10"
    env["ADAPTIVE_SAFETY_FACTOR"] = "1.0"

    subprocess.run([str(target_script)], check=True, env=env)

    kpi_path = logs_dir / "daily_kpi.csv"
    assert kpi_path.exists()
    rows = kpi_path.read_text(encoding="utf-8").strip().splitlines()
    fields = rows[-1].split(",")
    pairs_selected = int(fields[4].strip())

    # target=10 with adaptive expected_per_pair=1 and cap=10 -> 10 pairs selected.
    assert pairs_selected == 10
