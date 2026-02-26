import csv
import pathlib

import pytest

import send_cold_emails as sce


class DummySMTP:
    def __init__(self, *args, **kwargs):
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, *_args, **_kwargs):
        return None

    def sendmail(self, _from_addr, to_addrs, _msg):
        self.sent.append(tuple(to_addrs))


@pytest.mark.parametrize(
    "filename, expected_town, expected_service",
    [
        (
            "leads_Colorado_Springs_CO_Fence_Installation_Repair_NO_WEBSITE_2026-02-26.csv",
            "Colorado Springs Co",
            "Fence Installation Repair",
        ),
        (
            "no_website_emails_san-diego_window-cleaning_2026-02-26.csv",
            "San Diego",
            "window cleaning",
        ),
        (
            "totally_unknown_pattern.csv",
            "Your Town",
            "Your Service",
        ),
    ],
)
def test_parse_context_from_filename(filename, expected_town, expected_service):
    town, service = sce.parse_context_from_filename(filename)
    assert town == expected_town
    assert service == expected_service


@pytest.mark.parametrize(
    "from_value, expected",
    [
        ("Example Person <person@example.com>", "person@example.com"),
        ("sales@example.com", "sales@example.com"),
        ("No Email Here", ""),
    ],
)
def test_extract_email_address(from_value, expected):
    assert sce.extract_email_address(from_value) == expected


def test_daily_cap_short_circuits_send(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path
    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 2)

    with open(sce.DAILY_SENT_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["a@example.com"])
        writer.writerow(["b@example.com"])

    sce.send_cold_emails(csv_file=str(data_dir / "missing.csv"))
    out = capsys.readouterr().out
    assert "Daily cap reached" in out


def test_suppression_list_skips_addresses(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails"])
        writer.writeheader()
        writer.writerow({"name": "Suppressed Biz", "emails": "blocked@example.com"})
        writer.writerow({"name": "Allowed Biz", "emails": "ok@example.com"})

    suppressions = data_dir / "suppressions.csv"
    with open(suppressions, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["blocked@example.com", "manual", "2026-02-26T10:00:00"])

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(suppressions))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("ok@example.com",) in smtp.sent
    assert ("blocked@example.com",) not in smtp.sent


def test_append_to_suppressions_is_idempotent(tmp_path, monkeypatch):
    suppressions = pathlib.Path(tmp_path) / "suppressions.csv"
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(suppressions))

    sce.append_to_suppressions("same@example.com", reason="manual")
    sce.append_to_suppressions("same@example.com", reason="manual")

    with open(suppressions, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 1
    assert rows[0][0] == "same@example.com"


def test_score_lead_prefers_business_domains():
    row = {"name": "Acme Plumbing", "notes": "", "website": ""}
    assert sce.score_lead(row, "owner@acmeplumbing.com") >= 3


def test_score_lead_penalizes_existing_website():
    row = {"name": "Acme Plumbing", "notes": "", "website": "https://acme.com"}
    assert sce.score_lead(row, "owner@acmeplumbing.com") < 3
