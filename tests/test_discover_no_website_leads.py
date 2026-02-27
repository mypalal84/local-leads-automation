import importlib.util
import pathlib
import uuid

import pandas as pd


def load_discover_module(home_dir: pathlib.Path):
    module_path = pathlib.Path(__file__).resolve().parents[1] / "src" / "discover_no_website_leads.py"
    module_name = f"discover_no_website_leads_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__["__name__"] = module_name
    spec.loader.exec_module(module)
    return module


def test_archive_old_data_moves_only_lead_files(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    data_dir = home / "Scripts" / "Daily_Leads" / "data"
    data_dir.mkdir(parents=True)

    lead_file = data_dir / "leads_city_service_NO_WEBSITE_2026-02-26.csv"
    no_site_file = data_dir / "no_website_emails_city_service_2026-02-26.csv"
    sent_log = data_dir / "sent_log.csv"

    lead_file.write_text("name\nDemo\n", encoding="utf-8")
    no_site_file.write_text("name\nDemo\n", encoding="utf-8")
    sent_log.write_text("demo@example.com\n", encoding="utf-8")

    module = load_discover_module(home)
    module.archive_old_data()

    archive_root = pathlib.Path(module.ARCHIVE_DIR)
    session_dirs = [p for p in archive_root.iterdir() if p.is_dir()]
    assert session_dirs, "Expected archive session directory to be created"

    archived_names = {p.name for p in session_dirs[0].iterdir()}
    assert lead_file.name in archived_names
    assert no_site_file.name in archived_names
    assert sent_log.exists(), "sent_log.csv should not be archived"


def test_is_probably_real_website_directory_domains_false(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.is_probably_real_website("https://www.yelp.com/biz/demo", "Demo Biz") is False


def test_is_probably_real_website_non_directory_domain_true(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.is_probably_real_website("https://bayviewroofinginc.com/", "Bay View Roofing") is True


def test_discover_writes_filtered_output(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DISCOVERY_PROVIDER", "serper")
    module = load_discover_module(home)

    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "run_serper_search", lambda _q: [
        {
            "title": "[PDF] When East meets West - Yale University",
            "link": "https://www.yale.edu/some-paper.pdf",
            "snippet": "Yale University PDF",
        },
        {
            "title": "250k Construction Jobs, Employment | Indeed",
            "link": "https://www.indeed.com/jobs?q=construction",
            "snippet": "Construction jobs and employment listings",
        },
        {
            "title": "Good Lead",
            "link": "https://example-lead.com",
            "snippet": "Local service provider",
        },
        {
            "title": "Good Lead",
            "link": "https://example-lead.com/dup",
            "snippet": "Duplicate title should be removed",
        },
        {
            "title": "Snippet Domain Lead",
            "link": "https://no-site.example",
            "snippet": "visit www.realwebsite.com for details",
        },
    ])
    monkeypatch.setattr(module, "is_probably_real_website", lambda _link, _name="": False)

    out_path = module.discover("Fence Installation / Repair", "Colorado Springs, CO")
    assert out_path is not None

    out_file = pathlib.Path(out_path)
    assert out_file.exists()

    df = pd.read_csv(out_file)
    assert list(df.columns) == ["name", "link", "website", "email", "notes"]
    assert len(df) == 1
    assert df.iloc[0]["name"] == "Good Lead"


def test_discover_removes_stale_output_when_no_leads(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DISCOVERY_PROVIDER", "serper")
    module = load_discover_module(home)

    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "run_serper_search", lambda _q: [
        {
            "title": "Acme Roofing",
            "link": "https://acme-roofing.com",
            "snippet": "Local roofing",
        }
    ])
    monkeypatch.setattr(module, "is_probably_real_website", lambda _link, _name="": True)

    service = "Roofers"
    town = "San Jose, CA"
    safe_city = "San_Jose_CA"
    safe_service = "Roofers"
    out_path = pathlib.Path(module.DATA_DIR) / f"leads_{safe_city}_{safe_service}_NO_WEBSITE_{module.date.today().strftime('%Y-%m-%d')}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("name,link,website,email,notes\nold,https://old.com,,,old\n", encoding="utf-8")

    result = module.discover(service, town)
    assert result is None
    assert not out_path.exists()


def test_should_skip_non_business_result_flags_pdf_and_jobboard(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.should_skip_non_business_result(
        "[PDF] University Research",
        "https://www.yale.edu/research/paper.pdf",
        "PDF file"
    ) is True
    assert module.should_skip_non_business_result(
        "Construction Jobs | Indeed",
        "https://www.indeed.com/jobs?q=construction",
        "Employment listings"
    ) is True
    assert module.should_skip_non_business_result(
        "Acme Plumbing",
        "https://acme-plumbing-denver.com",
        "Local plumbing service"
    ) is False


def test_should_skip_non_business_result_flags_aggregator_domains(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.should_skip_non_business_result(
        "TOP 10 BEST Landscaping Services",
        "https://www.yelp.com/search?find_desc=landscaping",
        "Yelp listings"
    ) is True
    assert module.should_skip_non_business_result(
        "Top-Rated Tree Services",
        "https://www.homeadvisor.com/c.tree-service",
        "HomeAdvisor providers"
    ) is True


def test_should_skip_non_business_result_flags_tiktok_domain(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.should_skip_non_business_result(
        "Our roofer is putting in the work! ... | TikTok",
        "https://www.tiktok.com/@caruzoroofingcontractors/video/7550877614882213134",
        "Short video clip"
    ) is True


def test_should_skip_non_business_result_flags_seo_marketing_content(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    assert module.should_skip_non_business_result(
        "San Jose Roofing Companies SEO",
        "https://roofing.bullberry.com/services/city/san-jose-ca",
        "local SEO for roofers in San Jose"
    ) is True


def test_run_serper_search_uses_cache(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    cache_dir = pathlib.Path(tmp_path) / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(module, "SERPER", "test-serper-key")

    calls = {"count": 0}

    def fake_retry(func, *_args, **_kwargs):
        calls["count"] += 1
        return [{"title": "Lead", "link": "https://example.com", "snippet": ""}]

    monkeypatch.setattr(module, "retry_request", fake_retry)

    query = "plumber denver"
    first = module.run_serper_search(query)
    second = module.run_serper_search(query)

    assert first == second
    assert calls["count"] == 1


def test_increment_api_counter_updates_metrics_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    metrics_file = pathlib.Path(tmp_path) / "run_metrics.json"
    metrics_file.write_text('{"google_places": 0, "serper": 0, "hunter": 0}', encoding="utf-8")
    monkeypatch.setattr(module, "RUN_METRICS_FILE", str(metrics_file))

    module.increment_api_counter("serper")

    payload = __import__("json").loads(metrics_file.read_text(encoding="utf-8"))
    assert payload["serper"] == 1


def test_discover_uses_google_places_when_key_present(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-google-key")
    monkeypatch.delenv("DISCOVERY_PROVIDER", raising=False)

    module = load_discover_module(home)

    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "run_google_places_text_search", lambda _s, _t: [
        {
            "name": "places/abc123",
            "id": "abc123",
            "displayName": {"text": "No Site Roofing"},
            "formattedAddress": "123 Main St, San Jose, CA",
            "googleMapsUri": "https://maps.google.com/?cid=123",
        }
    ])
    monkeypatch.setattr(module, "get_google_place_details", lambda _pid: {
        "websiteUri": "",
        "googleMapsUri": "https://maps.google.com/?cid=123",
        "formattedAddress": "123 Main St, San Jose, CA",
    })

    out_path = module.discover("Roofers", "San Jose, CA")
    assert out_path is not None

    df = pd.read_csv(out_path)
    assert len(df) == 1
    assert df.iloc[0]["name"] == "No Site Roofing"


def test_discover_google_places_skips_business_with_website(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-google-key")
    monkeypatch.delenv("DISCOVERY_PROVIDER", raising=False)

    module = load_discover_module(home)

    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "run_google_places_text_search", lambda _s, _t: [
        {
            "name": "places/def456",
            "id": "def456",
            "displayName": {"text": "Has Site Roofing"},
            "formattedAddress": "456 Market St, San Jose, CA",
            "googleMapsUri": "https://maps.google.com/?cid=456",
        }
    ])
    monkeypatch.setattr(module, "get_google_place_details", lambda _pid: {
        "websiteUri": "https://hassiteroofing.com",
        "googleMapsUri": "https://maps.google.com/?cid=456",
        "formattedAddress": "456 Market St, San Jose, CA",
    })

    out_path = module.discover("Roofers", "San Jose, CA")
    assert out_path is None
