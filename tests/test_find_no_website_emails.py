import csv
import json
import pathlib
from datetime import datetime, timedelta

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
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", False)

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


def test_search_serper_uses_cache(tmp_path, monkeypatch):
    cache_dir = pathlib.Path(tmp_path) / "cache"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr(enrich_mod, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(enrich_mod, "SERPER", "test-serper-key")

    calls = {"count": 0}

    def fake_retry(func, *_args, **_kwargs):
        calls["count"] += 1
        return ["https://example.com"]

    monkeypatch.setattr(enrich_mod, "retry_request", fake_retry)

    q = "demo query"
    assert enrich_mod.search_serper(q) == ["https://example.com"]
    assert enrich_mod.search_serper(q) == ["https://example.com"]
    assert calls["count"] == 1


def test_hunter_lookup_uses_cache(tmp_path, monkeypatch):
    cache_dir = pathlib.Path(tmp_path) / "cache"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr(enrich_mod, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(enrich_mod, "HUNTER", "test-hunter-key")

    calls = {"count": 0}

    def fake_retry(func, *_args, **_kwargs):
        calls["count"] += 1
        return ["owner@example.com"]

    monkeypatch.setattr(enrich_mod, "retry_request", fake_retry)

    domain = "example.com"
    assert enrich_mod.hunter_email_lookup(domain) == ["owner@example.com"]
    assert enrich_mod.hunter_email_lookup(domain) == ["owner@example.com"]
    assert calls["count"] == 1


def test_prune_expired_cache_removes_old_files(tmp_path, monkeypatch):
    cache_dir = pathlib.Path(tmp_path) / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(enrich_mod, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(enrich_mod, "CACHE_TTL_DAYS", 7)

    old_file = cache_dir / "hunter_old.json"
    fresh_file = cache_dir / "hunter_fresh.json"

    old_payload = {
        "created_at": (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds"),
        "value": ["a@example.com"],
    }
    fresh_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "value": ["b@example.com"],
    }

    old_file.write_text(json.dumps(old_payload), encoding="utf-8")
    fresh_file.write_text(json.dumps(fresh_payload), encoding="utf-8")

    removed = enrich_mod.prune_expired_cache()
    assert removed == 1
    assert not old_file.exists()
    assert fresh_file.exists()


def test_increment_api_counter_updates_metrics_file(tmp_path, monkeypatch):
    metrics_file = pathlib.Path(tmp_path) / "run_metrics.json"
    metrics_file.write_text('{"google_places": 0, "serper": 1, "hunter": 0}', encoding="utf-8")
    monkeypatch.setattr(enrich_mod, "RUN_METRICS_FILE", str(metrics_file))

    enrich_mod.increment_api_counter("hunter")

    payload = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert payload["serper"] == 1
    assert payload["hunter"] == 1


def test_pre_enrich_score_filter_skips_api_calls_for_low_score_lead(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "LEAD_SCORE_THRESHOLD", 3)
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", True)

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes"])
        writer.writeheader()
        writer.writerow({"name": "Solo", "emails": "", "website": "", "notes": ""})

    calls = {"search": 0, "hunter": 0}

    def fake_search(_query):
        calls["search"] += 1
        return ["http://example.com"]

    def fake_hunter(_domain):
        calls["hunter"] += 1
        return ["owner@example.com"]

    monkeypatch.setattr(enrich_mod, "search_serper", fake_search)
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", fake_hunter)
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path == str(in_path)
    assert calls["search"] == 0
    assert calls["hunter"] == 0


def test_pre_enrich_score_filter_allows_api_calls_for_eligible_lead(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "LEAD_SCORE_THRESHOLD", 3)
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", True)

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes"])
        writer.writeheader()
        writer.writerow({"name": "Bright Fences", "emails": "", "website": "", "notes": "no website"})

    calls = {"search": 0, "hunter": 0}

    def fake_search(_query):
        calls["search"] += 1
        return ["http://example.com"]

    def fake_hunter(_domain):
        calls["hunter"] += 1
        return ["owner@example.com"]

    monkeypatch.setattr(enrich_mod, "search_serper", fake_search)
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", fake_hunter)
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path == str(in_path)
    assert calls["search"] == 1
    assert calls["hunter"] == 1


def test_pre_enrich_base_score_ignores_nan_website():
    row = {"name": "Bright Fences", "notes": "", "website": float("nan")}
    assert enrich_mod.pre_enrich_base_score(row) == 1


def test_pre_enrich_base_score_penalizes_directory_domains():
    row = {
        "name": "Bright Fences",
        "notes": "",
        "website": "",
        "link": "https://www.zocdoc.com/dentists/sacramento-209566pm/4",
    }
    assert enrich_mod.pre_enrich_base_score(row) == 0


def test_existing_website_row_skips_api_calls(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", True)

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Directory Listing",
                "emails": "",
                "website": "http://www.zocdoc.com",
                "notes": "",
                "link": "https://www.zocdoc.com/dentist/example",
            }
        )

    calls = {"search": 0, "hunter": 0}

    def fake_search(_query):
        calls["search"] += 1
        return ["http://example.com"]

    def fake_hunter(_domain):
        calls["hunter"] += 1
        return ["owner@example.com"]

    monkeypatch.setattr(enrich_mod, "search_serper", fake_search)
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", fake_hunter)
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path is None
    assert calls["search"] == 0
    assert calls["hunter"] == 0


def test_enrich_domain_match_guard_skips_when_serp_domain_matches_email_domain(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", False)

    service = "Personal Trainers"
    town = "Manchester, NH"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Get Fit NH",
                "emails": "",
                "website": "",
                "notes": "",
                "link": "https://maps.google.com/?cid=1",
            }
        )

    monkeypatch.setattr(enrich_mod, "search_serper", lambda _query: ["https://www.getfitnh.com/about"])
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", lambda _domain: ["meagan@getfitnh.com"])
    monkeypatch.setattr(enrich_mod, "is_confirmed_business_website", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town, max_leads=1)

    # Lead is skipped as website-positive via domain-match guard, so no enriched output remains.
    assert out_path is None


def test_business_name_matches_domain_true_for_get_fit_style_name():
    assert enrich_mod.business_name_matches_domain("Get Fit NH", "getfitnh.com") is True


def test_business_name_matches_domain_false_for_cross_company_domain():
    assert enrich_mod.business_name_matches_domain(
        "Down & Dirty Cleaning Services LLC",
        "corporatecleanservices.com",
    ) is False


def test_is_confirmed_business_website_rejects_directory_domain(monkeypatch):
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: True)
    assert enrich_mod.is_confirmed_business_website("https://www.houzz.com/professionals/example") is False


def test_is_confirmed_business_website_accepts_live_non_directory_domain(monkeypatch):
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda domain: domain == "callmilestone.com")
    assert enrich_mod.is_confirmed_business_website("https://callmilestone.com/duncanville/") is True


def test_is_confirmed_business_website_accepts_wixsite_hosted_domains(monkeypatch):
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    assert enrich_mod.is_confirmed_business_website("https://caldercitycleaning.wixsite.com/website") is True


def test_is_non_business_domain_flags_directory_sites():
    assert enrich_mod.is_non_business_domain("www.indeed.com") is True
    assert enrich_mod.is_non_business_domain("nextdoor.com") is True
    assert enrich_mod.is_non_business_domain("acmefencing.com") is False


def test_filter_viable_emails_excludes_non_business_domains():
    filtered = enrich_mod.filter_viable_emails(
        [
            "bbooth@yelp.com",
            "najiyakhan@instagram.com",
            "owner@acmefencing.com",
            "kmcnamara@nextdoor.com",
            "OWNER@acmefencing.com",
        ]
    )
    assert filtered == ["owner@acmefencing.com"]


def test_filter_viable_emails_excludes_full_social_notification_domain_list():
    filtered = enrich_mod.filter_viable_emails(
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
            "owner@acmefencing.com",
        ]
    )
    assert filtered == ["owner@acmefencing.com"]


def test_enrich_keeps_website_empty_when_email_found_on_unconfirmed_domain(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", False)

    service = "Fence Installation / Repair"
    town = "Colorado Springs, CO"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Acme Fencing",
                "emails": "",
                "website": "",
                "notes": "",
                "link": "",
            }
        )

    monkeypatch.setattr(enrich_mod, "search_serper", lambda _query: ["https://example.com/contact"])
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", lambda _domain: ["owner@acmefencing.com"])
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path == str(in_path)

    out_df = pd.read_csv(in_path)
    assert len(out_df) == 1
    assert out_df.loc[0, "emails"] == "owner@acmefencing.com"
    assert str(out_df.loc[0, "website"]).strip() in {"", "nan"}


def test_enrich_skips_non_business_email_domains(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", False)

    service = "Dry Cleaners"
    town = "Rochester, NY"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Local Cleaner",
                "emails": "",
                "website": "",
                "notes": "",
                "link": "",
            }
        )

    monkeypatch.setattr(enrich_mod, "search_serper", lambda _query: ["https://example-directory-result.com/contact"])
    monkeypatch.setattr(enrich_mod, "has_live_website", lambda _domain: False)
    monkeypatch.setattr(
        enrich_mod,
        "hunter_email_lookup",
        lambda _domain: [
            "bbooth@yelp.com",
            "najiyakhan@instagram.com",
            "owner@localcleaner.com",
            "kmcnamara@nextdoor.com",
        ],
    )
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path == str(in_path)

    out_df = pd.read_csv(in_path)
    assert len(out_df) == 1
    assert out_df.loc[0, "emails"] == "owner@localcleaner.com"


def test_enrich_skips_when_email_domain_has_live_website(tmp_path, monkeypatch):
    data_dir = pathlib.Path(tmp_path)
    monkeypatch.setattr(enrich_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(enrich_mod, "DATESTAMP", "2026-02-26")
    monkeypatch.setattr(enrich_mod, "PRE_ENRICH_SCORE_FILTER", False)

    service = "Martial Arts Schools"
    town = "Montgomery, AL"
    safe_town = enrich_mod.sanitize_for_filename(town)
    safe_service = enrich_mod.sanitize_for_filename(service)
    in_path = data_dir / f"leads_{safe_town}_{safe_service}_NO_WEBSITE_2026-02-26.csv"

    with open(in_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "emails", "website", "notes", "link"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Tiger Rock Martial Arts Montgomery",
                "emails": "",
                "website": "",
                "notes": "",
                "link": "",
            }
        )

    monkeypatch.setattr(enrich_mod, "search_serper", lambda _query: ["https://example-directory-result.com/contact"])
    monkeypatch.setattr(enrich_mod, "hunter_email_lookup", lambda _domain: ["bpadilla@tigerrockmartialarts.com"])
    monkeypatch.setattr(
        enrich_mod,
        "has_live_website",
        lambda domain: (domain or "").replace("www.", "") == "tigerrockmartialarts.com",
    )
    monkeypatch.setattr(enrich_mod.time, "sleep", lambda *_args, **_kwargs: None)

    out_path = enrich_mod.enrich(service, town)
    assert out_path is None
