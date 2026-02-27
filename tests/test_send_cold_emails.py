import csv
import pathlib
from email.message import EmailMessage

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
