import csv
import pathlib

import pandas as pd
import pytest

import find_no_website_emails as enrich_mod


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Colorado Springs, CO / Fence Installation", "Colorado_Springs_CO_Fence_Installation"),
        ("  Window / Door Installation ", "Window_Door_Installation"),
        ("St. Louis, MO", "St_Louis_MO"),
    ],
)
def test_sanitize_for_filename(raw, expected):
    assert enrich_mod.sanitize_for_filename(raw) == expected


def test_enrich_max_leads_zero_returns_early(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website"])
        writer.writeheader()
        writer.writerow({"name": "Demo Business", "emails": "", "website": ""})

    result = enrich_mod.enrich(service, town, max_leads=0)
    assert result == str(in_path)


def test_enrich_respects_max_leads_limit(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website"])
        writer.writeheader()
        writer.writerow({"name": "Biz One", "emails": "", "website": ""})
        writer.writerow({"name": "Biz Two", "emails": "", "website": ""})

    calls = {"search": 0}

    def fake_search(_query):
        calls["search"] += 1
        return ["http://example.com"]

    monkeypatch.setattr(enrich_mod, "search_serper", fake_search)
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", lambda _domain: ["owner@example.com"])
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town, max_leads=1)
    assert out_path == str(in_path)
    assert calls["search"] == 1

    out_df = pd.read_csv(in_path)
    assert len(out_df) == 1
