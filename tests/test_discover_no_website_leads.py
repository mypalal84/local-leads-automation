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


def test_discover_writes_filtered_output(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    module = load_discover_module(home)

    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "run_serper_search", lambda _q: [
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
