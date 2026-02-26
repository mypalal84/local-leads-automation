import pathlib

import pandas as pd

import daily_summary_report as dsr


class DummySMTP:
    def __init__(self, *_args, **_kwargs):
        self.logged_in = None
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, from_addr, to_addrs, message):
        self.sent.append((from_addr, tuple(to_addrs), message))


def test_build_summary_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(dsr, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(dsr, "TODAY", "2026-02-26")

    text = dsr.build_summary()
    assert "No 'no_website_emails' files found for 2026-02-26." in text


def test_build_summary_counts_files_and_emails(tmp_path, monkeypatch):
    monkeypatch.setattr(dsr, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(dsr, "TODAY", "2026-02-26")

    df1 = pd.DataFrame([
        {"name": "Biz 1", "emails": "a@example.com"},
        {"name": "Biz 2", "emails": None},
    ])
    df2 = pd.DataFrame([
        {"name": "Biz 3", "emails": "b@example.com"},
    ])

    df1.to_csv(tmp_path / "no_website_emails_city_service_2026-02-26.csv", index=False)
    df2.to_csv(tmp_path / "no_website_emails_other_service_2026-02-26.csv", index=False)

    text = dsr.build_summary()
    assert "Files processed : 2" in text
    assert "Total leads     : 3" in text
    assert "Emails found    : 2" in text


def test_send_summary_email_uses_smtp(monkeypatch):
    dummy = DummySMTP()
    monkeypatch.setattr(dsr, "EMAIL_FROM", "sender@example.com")
    monkeypatch.setattr(dsr, "EMAIL_PASS", "secret")
    monkeypatch.setattr(dsr, "EMAIL_TO", "owner@example.com")
    monkeypatch.setattr(dsr.smtplib, "SMTP_SSL", lambda *_args, **_kwargs: dummy)

    dsr.send_summary_email("hello summary")

    assert dummy.logged_in == ("sender@example.com", "secret")
    assert len(dummy.sent) == 1
    assert dummy.sent[0][0] == "sender@example.com"
    assert dummy.sent[0][1] == ("owner@example.com",)
    assert "hello summary" in dummy.sent[0][2]
