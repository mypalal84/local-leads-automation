import csv
import pathlib

import find_no_website_emails as enrich_mod


def test_sanitize_for_filename():
    raw = "Colorado Springs, CO / Fence Installation"
    assert enrich_mod.sanitize_for_filename(raw) == "Colorado_Springs_CO_Fence_Installation"


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
