import csv
import pathlib
from email.message import EmailMessage

import pytest

import send_cold_emails as sce


@pytest.fixture(autouse=True)
def _disable_website_guard_by_default(monkeypatch):
    monkeypatch.setattr(sce, "PRE_SEND_WEBSITE_GUARD", False)


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


def test_append_logs_include_lead_score_metadata(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    sent_log = data_dir / "sent_log.csv"
    daily_log = data_dir / "daily_sent_2026-02-26.csv"

    monkeypatch.setattr(sce, "SENT_LOG", str(sent_log))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(daily_log))

    sce.append_to_log("owner@example.com", lead_score=4, source_file="/tmp/leads_example.csv")
    sce.append_to_daily_log("owner@example.com", lead_score=4, source_file="/tmp/leads_example.csv")

    with open(sent_log, newline="", encoding="utf-8") as f:
        sent_row = next(csv.reader(f))
    with open(daily_log, newline="", encoding="utf-8") as f:
        daily_row = next(csv.reader(f))

    assert sent_row[0] == "owner@example.com"
    assert sent_row[1] == "4"
    assert sent_row[3] == "leads_example.csv"
    assert daily_row[0] == "owner@example.com"
    assert daily_row[1] == "4"
    assert daily_row[3] == "leads_example.csv"


def test_load_sent_log_ignores_header_like_rows(tmp_path, monkeypatch):
    sent_log = pathlib.Path(tmp_path) / "sent_log.csv"
    with open(sent_log, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["email", "lead_score", "sent_at", "source_file"])
        writer.writerow(["real@example.com", "3", "2026-03-08T12:00:00", "leads.csv"])

    monkeypatch.setattr(sce, "SENT_LOG", str(sent_log))
    loaded = sce.load_sent_log()

    assert loaded == {"real@example.com"}


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
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
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


def test_sender_skips_domain_when_hard_bounce_threshold_reached(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails"])
        writer.writeheader()
        writer.writerow({"name": "Blocked Domain Biz", "emails": "owner@blocked.com"})
        writer.writerow({"name": "Allowed Domain Biz", "emails": "owner@okbiz.com"})

    suppressions = data_dir / "suppressions.csv"
    with open(suppressions, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["a@blocked.com", "delivery_failure_hard", "2026-03-08T07:00:00"])
        writer.writerow(["b@blocked.com", "delivery_failure_hard", "2026-03-08T07:01:00"])

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(suppressions))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "HARD_BOUNCE_DOMAIN_SUPPRESS_THRESHOLD", 2)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("owner@okbiz.com",) in smtp.sent
    assert ("owner@blocked.com",) not in smtp.sent


def test_sender_pre_send_website_guard_skips_live_site_domain(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Get Fit NH",
                "emails": "meagan@getfitnh.com",
                "website": "",
                "notes": "",
                "link": "https://maps.google.com/?cid=1",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "PRE_SEND_WEBSITE_GUARD", True)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce, "has_live_business_website", lambda domain: domain == "getfitnh.com")
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert smtp.sent == []


def test_sender_pre_send_website_guard_does_not_apply_for_unrelated_corporate_domain(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Coffee Plaza Barber Shop",
                "emails": "katie.stock@fresha.com",
                "website": "",
                "notes": "",
                "link": "https://maps.google.com/?cid=1",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "PRE_SEND_WEBSITE_GUARD", True)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce, "has_live_business_website", lambda domain: domain == "fresha.com")
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("katie.stock@fresha.com",) in smtp.sent


def test_append_to_suppressions_is_idempotent(tmp_path, monkeypatch):
    suppressions = pathlib.Path(tmp_path) / "suppressions.csv"
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(suppressions))

    sce.append_to_suppressions("same@example.com", reason="manual")
    sce.append_to_suppressions("same@example.com", reason="manual")

    with open(suppressions, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 1
    assert rows[0][0] == "same@example.com"


def test_load_hard_bounce_domain_blocklist_counts_only_hard_bounces(tmp_path, monkeypatch):
    suppressions = pathlib.Path(tmp_path) / "suppressions.csv"
    with open(suppressions, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["a@blocked.com", "delivery_failure_hard", "2026-03-08T07:00:00"])
        writer.writerow(["b@blocked.com", "delivery_failure_hard", "2026-03-08T07:01:00"])
        writer.writerow(["c@blocked.com", "negative_reply", "2026-03-08T07:02:00"])
        writer.writerow(["d@other.com", "delivery_failure_hard", "2026-03-08T07:03:00"])

    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(suppressions))

    blocked_domains = sce.load_hard_bounce_domain_blocklist(2)
    assert blocked_domains == {"blocked.com"}


def test_pending_queue_reuses_qualified_unsent_leads(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes"])
        writer.writeheader()
        writer.writerow({"name": "First Biz", "emails": "first@examplebiz.com", "website": "", "notes": ""})
        writer.writerow({"name": "Second Biz", "emails": "second@examplebiz.com", "website": "", "notes": ""})

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "PENDING_LEADS_FILE", str(data_dir / "pending_leads.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(sce, "DRY_RUN", False)

    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 1)
    smtp_first = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp_first)
    sce.send_cold_emails(csv_file=str(csv_path))

    assert len(smtp_first.sent) == 1
    with open(sce.PENDING_LEADS_FILE, newline="", encoding="utf-8") as f:
        pending_rows = list(csv.DictReader(f))
    assert len(pending_rows) == 1
    assert pending_rows[0]["emails"] == "second@examplebiz.com"
    assert pending_rows[0]["lead_score"] != ""

    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-27.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 5)
    smtp_second = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp_second)
    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("second@examplebiz.com",) in smtp_second.sent
    pending_path = pathlib.Path(sce.PENDING_LEADS_FILE)
    assert pending_path.exists()
    with open(pending_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == []


def test_sender_dry_run_prioritizes_highest_score_first(tmp_path, monkeypatch, capsys):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Low Score Biz",
                "emails": "low@gmail.com",
                "website": "",
                "notes": "",
                "link": "",
            }
        )
        writer.writerow(
            {
                "name": "High Score Business",
                "emails": "high@highscorebiz.com",
                "website": "",
                "notes": "under construction",
                "link": "",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "PENDING_LEADS_FILE", str(data_dir / "pending_leads.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "DRY_RUN", True)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")

    sce.send_cold_emails(csv_file=str(csv_path))
    out = capsys.readouterr().out

    high_idx = out.index("[DRY-SEND] High Score Business")
    low_idx = out.index("[DRY-SEND] Low Score Biz")
    assert high_idx < low_idx


def test_resolve_row_context_uses_source_file_when_row_context_missing():
    row = {
        "emails": "amber@auroraplumbing.com",
        "__source_file": "data/leads_Seattle_WA_Plumbers_NO_WEBSITE_2026-02-27.csv",
        "__town": "",
        "__service": "",
    }

    town, service = sce.resolve_row_context(row, "Sacramento Ca", "Landscapers Lawn Care")

    assert town == "Seattle Wa"
    assert service == "Plumbers"


def test_policy_skipped_lead_is_pruned_from_pending_queue(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes"])
        writer.writeheader()
        writer.writerow({"name": "Acme Biz", "emails": "hello@acmebiz.com", "website": "", "notes": ""})

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "PENDING_LEADS_FILE", str(data_dir / "pending_leads.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", True)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(sce, "DRY_RUN", False)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert smtp.sent == []
    with open(sce.PENDING_LEADS_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == []


def test_score_lead_prefers_business_domains():
    row = {"name": "Acme Plumbing", "notes": "", "website": ""}
    assert sce.score_lead(row, "owner@acmeplumbing.com") >= 3


def test_score_lead_penalizes_existing_website():
    row = {"name": "Acme Plumbing", "notes": "", "website": "https://acme.com"}
    assert sce.score_lead(row, "owner@acmeplumbing.com") < 3


def test_score_lead_ignores_nan_website_value():
    row = {"name": "Acme Plumbing", "notes": "", "website": float("nan")}
    assert sce.score_lead(row, "owner@acmeplumbing.com") >= 3


def test_build_email_body_includes_unsubscribe_footer(monkeypatch):
    monkeypatch.setattr(sce, "UNSUBSCRIBE_FOOTER", "Reply STOP to unsubscribe.")
    body = sce.build_email_body("Acme", "Denver, CO", "Plumbing", contact_name="Alex")
    assert "Reply STOP to unsubscribe." in body


@pytest.mark.parametrize(
    "email_addr, expected_name",
    [
        ("amber@auroraplumbing.com", "Amber"),
        ("bryan@aqualityhvac.org", "Bryan"),
        ("colin@advancedheatingandcooling.com", "Colin"),
        ("andy.maclean@owenscorning.com", "Andy"),
        ("morgan@jazzhouse.org", "Morgan"),
        ("veronica.hart@zoominfo.com", "Veronica"),
        ("info@company.com", "there"),
        ("help@bbb.org", "there"),
        ("bbooth@yelp.com", "there"),
        ("jrace@allenthomasgroup.com", "there"),
    ],
)
def test_extract_contact_name_matrix(email_addr, expected_name):
    assert sce.extract_contact_name(email_addr) == expected_name


def test_build_subject_line_avoids_contact_name_template_for_unknown_name(monkeypatch):
    monkeypatch.setattr(sce.random, "choice", lambda seq: seq[0])
    subject = sce.build_subject_line("Acme Roofing", "there", "San Jose Ca")
    assert "there," not in subject.lower()


def test_build_subject_line_can_use_contact_name_template_when_known(monkeypatch):
    monkeypatch.setattr(sce.random, "choice", lambda _seq: "{contact_name}, quick idea for {business}")
    subject = sce.build_subject_line("Acme Roofing", "Andy", "San Jose Ca")
    assert subject == "Andy, quick idea for Acme Roofing"


def test_build_subject_line_town_template_has_no_double_comma(monkeypatch):
    monkeypatch.setattr(sce.random, "choice", lambda _seq: "{town} lead-gen idea for {business}")
    subject = sce.build_subject_line("Acme Roofing", "there", "San Jose, CA")
    assert subject == "San Jose, CA lead-gen idea for Acme Roofing"
    assert ",," not in subject


def test_build_email_body_uses_contact_name():
    body = sce.build_email_body("Acme Roofing", "Denver, CO", "Roofers", contact_name="Andy")
    assert body.startswith("Hi Andy,")


def test_rendered_email_end_to_end_regression(monkeypatch):
    row = {
        "name": "Bay View Roofing, Inc.: Roofing Experts in San Francisco | Yelp",
        "notes": "Trusted roofer serving Bay Area homeowners since 2008.",
        "link": "https://bayviewroofinginc.com",
        "website": "",
    }
    email_addr = "morgan@jazzhouse.org"

    contact_name = sce.extract_contact_name(email_addr)
    business = sce.clean_business_name(row["name"], recipient_email=email_addr)
    service = sce.infer_service_from_row(row, "Roofers")

    monkeypatch.setattr(sce.random, "choice", lambda _seq: "{town} lead-gen idea for {business}")
    subject = sce.build_subject_line(business=business, contact_name=contact_name, town="San Jose, CA")
    body = sce.build_email_body(
        business=business,
        town="San Jose, CA",
        service=service,
        contact_name=contact_name,
        notes=row["notes"],
    )

    assert subject == "San Jose, CA lead-gen idea for Bay View Roofing, Inc."
    assert ",," not in subject
    assert body.startswith("Hi Morgan,")
    assert "Noticed trusted roofer serving Bay Area homeowners since 2008." in body
    assert "for Bay View Roofing, Inc.?" in body


def test_format_town_for_copy_adds_state_comma():
    assert sce.format_town_for_copy("San Jose Ca") == "San Jose, CA"


def test_format_town_for_copy_keeps_existing_comma_format():
    assert sce.format_town_for_copy("San Jose, CA") == "San Jose, CA"


def test_infer_service_from_row_prefers_row_content():
    row = {
        "name": "Acme Plumbing LLC",
        "notes": "Emergency drain and sewer repair",
        "link": "",
        "website": "",
    }
    assert sce.infer_service_from_row(row, "Roofers") == "plumbing"


def test_infer_service_from_row_falls_back_when_unknown():
    row = {
        "name": "Acme Business",
        "notes": "Trusted local team",
        "link": "",
        "website": "",
    }
    assert sce.infer_service_from_row(row, "Roofers") == "Roofers"


def test_build_personalized_opener_prefers_notes():
    opener = sce.build_personalized_opener("Trusted roofer serving Bay Area homeowners since 2008.", "Roofers")
    assert opener.startswith("Noticed ")


def test_build_email_body_includes_personalized_opener_and_formatted_town():
    body = sce.build_email_body(
        "Bay View Roofing",
        "San Jose Ca",
        "Roofers",
        contact_name="Andy",
        notes="Trusted roofer serving Bay Area homeowners since 2008.",
    )
    assert "Hi Andy," in body
    assert "Noticed " in body
    assert "I help local owners like you launch professional, mobile‑friendly websites" in body


def test_build_personalized_opener_falls_back_for_caption_like_notes():
    opener = sce.build_personalized_opener(
        "Roofing installation above coastal homes with ocean view and clear sky",
        "Roofers",
        business="Bay View Roofing",
    )
    assert opener.startswith("I had a quick idea for helping Bay View Roofing")


def test_build_personalized_opener_avoids_low_signal_directory_notes():
    opener = sce.build_personalized_opener(
        "business directory",
        "Roofers",
        business="Acme Roofing",
    )
    assert "Noticed" not in opener
    assert "Acme Roofing" in opener


def test_build_email_body_uses_clearer_default_unsubscribe_copy(monkeypatch):
    monkeypatch.setattr(
        sce,
        "UNSUBSCRIBE_FOOTER",
        "If this isn't relevant, reply STOP and I'll remove you from future emails.",
    )
    body = sce.build_email_body("Acme", "Denver, CO", "Plumbing", contact_name="Alex")
    assert "If this isn't relevant, reply STOP and I'll remove you from future emails." in body


def test_clean_business_name_removes_directory_suffixes():
    raw = "Bay View Roofing, Inc.: Roofing Experts in San Francisco | Yelp"
    assert sce.clean_business_name(raw) == "Bay View Roofing, Inc."


def test_clean_business_name_splits_common_glued_suffixes():
    assert sce.clean_business_name("allenthomasgroup") == "Allenthomas Group"


def test_clean_business_name_falls_back_to_recipient_domain_when_missing():
    assert sce.clean_business_name("", recipient_email="jrace@allenthomasgroup.com") == "Allen Thomas Group"


@pytest.mark.parametrize(
    "email_addr, expected",
    [
        ("veronica.hart@zoominfo.com", "ZoomInfo"),
        ("publicrelations@homeadvisor.com", "HomeAdvisor"),
        ("acurls@consumeraffairs.com", "ConsumerAffairs"),
        ("andy.maclean@owenscorning.com", "Owens Corning"),
        ("help@bbb.org", "BBB"),
    ],
)
def test_clean_business_name_brand_casing_from_domain(email_addr, expected):
    assert sce.clean_business_name("", recipient_email=email_addr) == expected


def test_build_service_cta_line_points_to_website():
    roofing_cta = sce.build_service_cta_line("Roofers")
    dental_cta = sce.build_service_cta_line("Dentists")
    assert roofing_cta == "If you're curious, you can see my work at www.zbadigital.com."
    assert dental_cta == roofing_cta


def test_domain_cap_limits_sends_per_domain(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails"])
        writer.writeheader()
        writer.writerow({"name": "Biz One", "emails": "owner1@same-domain.com"})
        writer.writerow({"name": "Biz Two", "emails": "owner2@same-domain.com"})

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 1)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert len(smtp.sent) == 1


def test_block_generic_inboxes(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails"])
        writer.writeheader()
        writer.writerow({"name": "Generic Biz", "emails": "info@example.com"})
        writer.writerow({"name": "Owner Biz", "emails": "owner@example.com"})

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", True)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("owner@example.com",) in smtp.sent
    assert ("info@example.com",) not in smtp.sent


def test_sender_dry_run_skips_smtp_send(tmp_path, monkeypatch, capsys):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Roofers_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "notes", "website", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Bay View Roofing, Inc. | Yelp",
                "emails": "owner@bayviewroofinginc.com",
                "notes": "Trusted roofer serving local homeowners since 2008.",
                "website": "",
                "link": "https://www.bayviewroofinginc.com",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "DRY_RUN", True)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: {"should_not_be_called@example.com"})

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))
    out = capsys.readouterr().out

    assert "[DRY-SEND]" in out
    assert "[DRY-BODY]" in out
    assert "skipping reply-check cleanup" in out
    assert smtp.sent == []


def test_sender_skips_rows_with_existing_website(tmp_path, monkeypatch, capsys):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Roofers_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "notes", "website", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Bay View Roofing, Inc.",
                "emails": "owner@bayviewroofinginc.com",
                "notes": "Trusted roofer serving local homeowners since 2008.",
                "website": "https://www.bayviewroofinginc.com",
                "link": "https://www.bayviewroofinginc.com",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "DRY_RUN", False)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))
    out = capsys.readouterr().out

    assert "[WEBSITE] Skipping owner@bayviewroofinginc.com" in out
    assert smtp.sent == []


def test_skip_reply_check_cleanup_in_live_mode(tmp_path, monkeypatch, capsys):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Roofers_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "notes", "website", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Bay View Roofing, Inc.",
                "emails": "owner@bayviewroofinginc.com",
                "notes": "Trusted roofer serving local homeowners since 2008.",
                "website": "",
                "link": "https://www.bayviewroofinginc.com",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", False)
    monkeypatch.setattr(sce, "DRY_RUN", False)
    monkeypatch.setattr(sce, "SKIP_REPLY_CHECK_CLEANUP", True)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    called = {"fetch": 0}

    def fake_fetch_replies():
        called["fetch"] += 1
        return {"owner@bayviewroofinginc.com"}

    monkeypatch.setattr(sce, "fetch_replies", fake_fetch_replies)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))
    out = capsys.readouterr().out

    assert ("owner@bayviewroofinginc.com",) in smtp.sent
    assert "SKIP_REPLY_CHECK_CLEANUP enabled" in out
    assert called["fetch"] == 0


def test_is_auto_reply_detects_subject_token():
    msg = EmailMessage()
    assert sce.is_auto_reply(msg, "Automatic reply: Out of office") is True


def test_is_auto_reply_detects_auto_submitted_header():
    msg = EmailMessage()
    msg["Auto-Submitted"] = "auto-replied"
    assert sce.is_auto_reply(msg, "Re: hello") is True


def test_processed_message_ids_roundtrip(tmp_path, monkeypatch):
    ids_file = pathlib.Path(tmp_path) / "processed_reply_message_ids.csv"
    monkeypatch.setattr(sce, "PROCESSED_REPLY_IDS_FILE", str(ids_file))

    sce.append_processed_message_id("<abc123@example.com>")
    sce.append_processed_message_id("<def456@example.com>")

    values = sce.load_processed_message_ids()
    assert "<abc123@example.com>" in values
    assert "<def456@example.com>" in values


def test_is_delivery_status_notification_by_subject():
    msg = EmailMessage()
    assert sce.is_delivery_status_notification(msg, "Delivery incomplete") is True


def test_is_delivery_status_notification_message_not_delivered_subject():
    msg = EmailMessage()
    assert sce.is_delivery_status_notification(msg, "Message not delivered") is True


def test_extract_bounced_recipient_from_final_recipient_header_text():
    msg = EmailMessage()
    body = "Final-Recipient: rfc822; info@awesomeland.org"
    assert sce.extract_bounced_recipient(msg, body) == "info@awesomeland.org"


def test_extract_bounced_recipient_from_for_clause():
    msg = EmailMessage()
    body = "There was a temporary problem delivering your message to info@awesomeland.org"
    assert sce.extract_bounced_recipient(msg, body) == "info@awesomeland.org"


def test_is_valid_email_syntax():
    assert sce.is_valid_email_syntax("owner@example.com") is True
    assert sce.is_valid_email_syntax("bad-address") is False


def test_should_send_to_email_rejects_no_mx(monkeypatch):
    monkeypatch.setattr(sce, "MX_CACHE", {})
    monkeypatch.setattr(sce, "has_mx_record", lambda _domain: False)
    ok, reason = sce.should_send_to_email("owner@example.com")
    assert ok is False
    assert reason == "no_mx"


def test_classify_bounce_type_hard_and_soft():
    assert sce.classify_bounce_type("Delivery failed", "550 5.1.1 user unknown") == "hard"
    assert sce.classify_bounce_type("Delivery delayed", "451 temporary issue") == "soft"


def test_classify_bounce_type_connection_refused_is_hard():
    body = "The recipient server did not accept our requests to connect. FAILED_PRECONDITION: connect error (111): Connection refused"
    assert sce.classify_bounce_type("Message not delivered", body) == "hard"


def test_classify_bounce_type_recipient_not_found_is_hard():
    body = "550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient adame@zillow.com not found by SMTP address lookup"
    assert sce.classify_bounce_type("Message not delivered", body) == "hard"


def test_handle_bounce_event_hard_suppresses_once(monkeypatch, capsys):
    calls = {"count": 0}

    def fake_append(email_addr, reason=""):
        calls["count"] += 1
        assert email_addr == "info@awesomeland.org"
        assert reason == "delivery_failure_hard"

    monkeypatch.setattr(sce, "append_to_suppressions", fake_append)

    seen = set()
    first = sce.handle_bounce_event("info@awesomeland.org", "hard", seen_bounce_events=seen)
    second = sce.handle_bounce_event("info@awesomeland.org", "hard", seen_bounce_events=seen)

    out = capsys.readouterr().out
    assert first is True
    assert second is False
    assert calls["count"] == 1
    assert out.count("Hard bounce suppressed: info@awesomeland.org") == 1


def test_handle_bounce_event_soft_logs_once(monkeypatch, capsys):
    monkeypatch.setattr(sce, "append_to_suppressions", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not suppress soft bounce")))

    seen = set()
    first = sce.handle_bounce_event("info@organiccarpetcare.com", "soft", seen_bounce_events=seen)
    second = sce.handle_bounce_event("info@organiccarpetcare.com", "soft", seen_bounce_events=seen)

    out = capsys.readouterr().out
    assert first is True
    assert second is False
    assert out.count("soft bounce detected: info@organiccarpetcare.com") == 1


def test_handle_bounce_event_unknown_suppresses_when_enabled(monkeypatch, capsys):
    calls = {"count": 0}

    def fake_append(email_addr, reason=""):
        calls["count"] += 1
        assert email_addr == "info@awesomeland.org"
        assert reason == "delivery_failure_unknown"

    monkeypatch.setattr(sce, "append_to_suppressions", fake_append)
    monkeypatch.setattr(sce, "AUTO_SUPPRESS_UNKNOWN_BOUNCES", True)

    seen = set()
    first = sce.handle_bounce_event("info@awesomeland.org", "unknown", seen_bounce_events=seen)
    second = sce.handle_bounce_event("info@awesomeland.org", "unknown", seen_bounce_events=seen)

    out = capsys.readouterr().out
    assert first is True
    assert second is False
    assert calls["count"] == 1
    assert out.count("Unknown bounce suppressed: info@awesomeland.org") == 1


def test_is_negative_reply_text_detects_stop_in_actual_reply_line():
    subject = "Re: FastTrack Garage Door's Services + mobile site idea"
    body = "STOP\n\nVon: alex@zbadigital.com <alex@zbadigital.com>\nDatum: Dienstag"
    assert sce.is_negative_reply_text(subject, body) is True


def test_is_negative_reply_text_ignores_quoted_footer_stop_phrase():
    subject = "Re: FastTrack Garage Door's Services + mobile site idea"
    body = (
        "Thanks, maybe later.\n\n"
        "From: alex@zbadigital.com <alex@zbadigital.com>\n"
        "If this isn't relevant, reply STOP and I'll remove you from future emails."
    )
    assert sce.is_negative_reply_text(subject, body) is False


def test_remove_from_log_handles_multicolumn_rows(tmp_path, monkeypatch):
    sent_log = pathlib.Path(tmp_path) / "sent_log.csv"
    with open(sent_log, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["first@example.com", "4", "2026-03-10T07:00:00", "leads_a.csv"])
        writer.writerow(["reply@example.com", "3", "2026-03-10T07:01:00", "leads_b.csv"])

    monkeypatch.setattr(sce, "SENT_LOG", str(sent_log))

    sce.remove_from_log({"reply@example.com"})

    with open(sent_log, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows == [["first@example.com", "4", "2026-03-10T07:00:00", "leads_a.csv"]]


def test_should_skip_non_business_lead_for_institutional_domain():
    row = {
        "name": "[PDF] When East meets West - Yale University",
        "link": "https://www.yale.edu/some-paper.pdf",
        "notes": "Yale University PDF",
        "website": "",
    }
    skip, reason = sce.should_skip_non_business_lead(row, "randall.gehle@va.gov")
    assert skip is True
    assert reason in {"institutional_domain", "non_business_text_hint"}


def test_should_skip_non_business_lead_for_jobboard_title():
    row = {
        "name": "250k Construction Jobs, Employment | Indeed",
        "link": "https://www.indeed.com/jobs?q=construction",
        "notes": "jobs and employment listings",
        "website": "",
    }
    skip, reason = sce.should_skip_non_business_lead(row, "vickil@indeed.com")
    assert skip is True
    assert reason in {"non_business_recipient_domain", "non_business_text_hint"}


@pytest.mark.parametrize(
    "email_addr, link",
    [
        ("bbooth@yelp.com", "https://www.yelp.com/biz/example"),
        ("designer@houzz.com", "https://www.houzz.com/professionals/example"),
        ("help@bbb.org", "https://www.bbb.org/us/fl/example"),
        ("publicrelations@homeadvisor.com", "https://www.homeadvisor.com/c.example"),
        ("veronica.hart@zoominfo.com", "https://www.manta.com/c/mx/example"),
        ("acurls@consumeraffairs.com", "https://www.consumeraffairs.com/homeowners/viking-refrigeration.html"),
    ],
)
def test_should_skip_non_business_lead_for_aggregator_domains(email_addr, link):
    row = {
        "name": "Directory Listing",
        "link": link,
        "notes": "",
        "website": "",
    }
    skip, reason = sce.should_skip_non_business_lead(row, email_addr)
    assert skip is True
    assert reason in {"non_business_recipient_domain", "non_business_source_domain"}


def test_should_skip_non_business_lead_for_directory_text_pattern():
    row = {
        "name": "Top 10 BEST Landscaping Services | Page 8",
        "link": "https://example.com/listings",
        "notes": "directory listing",
        "website": "",
    }
    skip, reason = sce.should_skip_non_business_lead(row, "owner@example-business.com")
    assert skip is True
    assert reason == "non_business_text_hint"


@pytest.mark.parametrize(
    "email_addr",
    [
        "alerts@facebook.com",
        "notice@facebookmail.com",
        "noreply@mail.instagram.com",
        "updates@linkedin.com",
        "notify@twitter.com",
        "notify@x.com",
        "msg@tiktok.com",
        "msg@tiktokv.com",
        "msg@pinterest.com",
        "msg@snapchat.com",
        "msg@youtube.com",
        "msg@support.google.com",
        "msg@reddit.com",
        "msg@whatsapp.com",
        "msg@discord.com",
        "msg@telegram.org",
        "support@carfax.com",
    ],
)
def test_should_skip_non_business_lead_for_social_notification_domains(email_addr):
    row = {
        "name": "Potential Lead",
        "link": "",
        "notes": "",
        "website": "",
    }
    skip, reason = sce.should_skip_non_business_lead(row, email_addr)
    assert skip is True
    assert reason in {"non_business_recipient_domain", "blocked_recipient_domain"}


def test_should_skip_domain_mismatch_blocks_unrelated_recipient_domain():
    row = {
        "name": "Bay View Roofing, Inc.",
        "website": "https://www.bayviewroofinginc.com/",
        "link": "https://bayviewroofinginc.com/",
        "notes": "",
    }
    skip, reason = sce.should_skip_domain_mismatch(row, "andy.maclean@owenscorning.com")
    assert skip is True
    assert reason.startswith("domain_mismatch:")


def test_should_skip_domain_mismatch_allows_matching_domain():
    row = {
        "name": "Bay View Roofing, Inc.",
        "website": "https://www.bayviewroofinginc.com/",
        "link": "https://bayviewroofinginc.com/",
        "notes": "",
    }
    skip, reason = sce.should_skip_domain_mismatch(row, "owner@bayviewroofinginc.com")
    assert skip is False
    assert reason == "ok"


def test_should_skip_domain_mismatch_ignores_google_maps_link_domain():
    row = {
        "name": "San Jose Roofing Co",
        "website": "",
        "link": "https://maps.google.com/?cid=9168630403281043056",
        "notes": "",
    }
    skip, reason = sce.should_skip_domain_mismatch(row, "info@sanjoseroofingco.com")
    assert skip is False
    assert reason == "ok"


def test_block_generic_inboxes_allows_business_info_when_enabled(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    csv_path = data_dir / "leads_Test_City_TC_Service_NO_WEBSITE_2026-02-26.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "link", "website", "notes"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "San Jose Roofing Co",
                "emails": "info@sanjoseroofingco.com",
                "link": "https://maps.google.com/?cid=9168630403281043056",
                "website": "",
                "notes": "2443 Alvin Ave, San Jose, CA 95121, USA",
            }
        )

    monkeypatch.setattr(sce, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sce, "SENT_LOG", str(data_dir / "sent_log.csv"))
    monkeypatch.setattr(sce, "REPLIES_FILE", str(data_dir / "replies.csv"))
    monkeypatch.setattr(sce, "SUPPRESSIONS_FILE", str(data_dir / "suppressions.csv"))
    monkeypatch.setattr(sce, "DAILY_SENT_LOG", str(data_dir / "daily_sent_2026-02-26.csv"))
    monkeypatch.setattr(sce, "DAILY_EMAIL_TARGET", 50)
    monkeypatch.setattr(sce, "LEAD_SCORE_THRESHOLD", 0)
    monkeypatch.setattr(sce, "PRE_SEND_VALIDATE_EMAILS", False)
    monkeypatch.setattr(sce, "MAX_EMAILS_PER_DOMAIN", 99)
    monkeypatch.setattr(sce, "BLOCK_GENERIC_INBOXES", True)
    monkeypatch.setattr(sce, "ALLOW_INFO_INBOX_WHEN_BUSINESS", True)
    monkeypatch.setattr(sce, "EMAIL_ADDR", "sender@example.com")
    monkeypatch.setattr(sce, "EMAIL_PASS", "dummy")
    monkeypatch.setattr(sce, "fetch_replies", lambda: set())
    monkeypatch.setattr(sce.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sce.random, "uniform", lambda *_args, **_kwargs: 0)

    smtp = DummySMTP()
    monkeypatch.setattr(sce.smtplib, "SMTP_SSL", lambda *args, **kwargs: smtp)

    sce.send_cold_emails(csv_file=str(csv_path))

    assert ("info@sanjoseroofingco.com",) in smtp.sent
