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
    source_script = project_root / "src" / "master_daily_pipeline.sh"
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

    subprocess.run([str(target_script)], check=True, env=env)

    kpi_path = logs_dir / "daily_kpi.csv"
    assert kpi_path.exists()

    rows = kpi_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) >= 2
    assert rows[0].startswith("date,timestamp,dry_run")
    assert ",true," in rows[-1]

    summary_log = (logs_dir / "summary.log").read_text(encoding="utf-8")
    assert "[KPI] Appended daily KPI row" in summary_log
