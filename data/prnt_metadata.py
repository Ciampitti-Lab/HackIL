import csv
import zipfile
from datetime import timedelta
from pathlib import Path

import openpyxl

RAW_ZIP = Path("data/raw/doi_10_5061_dryad_66t1g1k2g__v20210803.zip")
TMP_DIR = Path("data/tmp")

NEEDED_FILES = ["3.SiteHistoryandManagement_SI.xlsx"]

# S2_HARMONIZED (L1C) starts June 2015 and early coverage is too sparse.
# 2016 is the first year with reliable coverage across the US Midwest.
S2_MIN_YEAR = 2016

# Days after planting date to reach each V stage
V_STAGE_OFFSETS = {"V6": 30, "V7": 34, "V8": 38, "V9": 42, "V10": 46}


def ensure_extracted(needed: list[str]) -> None:
    """Extract files from raw zip to data/tmp/ only if not already present."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in needed if not (TMP_DIR / f).exists()]
    if not missing:
        print(f"All files already extracted to {TMP_DIR}/")
        return
    print(f"Extracting from {RAW_ZIP}: {missing}")
    with zipfile.ZipFile(RAW_ZIP) as zf:
        for name in missing:
            zf.extract(name, TMP_DIR)
    print("Extraction complete.")


def load_site_years() -> list[dict]:
    """Read planting dates and site metadata from 3.SiteHistoryandManagement_SI.xlsx."""
    wb = openpyxl.load_workbook(
        TMP_DIR / "3.SiteHistoryandManagement_SI.xlsx", read_only=True
    )
    ws = wb["History_Management"]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    col = {h: i for i, h in enumerate(headers)}

    site_years = []
    for row in rows[1:]:
        trial = row[col["Trial#"]]
        if trial is None:
            continue
        year = row[col["Year"]]
        if year < S2_MIN_YEAR:
            continue
        plant_date = row[col["PlantDate"]]
        if not plant_date or plant_date == ".":
            print(f"  Warning: Trial {trial} has no planting date, skipping.")
            continue

        entry = {
            "trial": trial,
            "year": row[col["Year"]],
            "state": row[col["State"]],
            "site": row[col["Site"]],
            "lat": row[col["Lat"]],
            "lon": row[col["Long"]],
            "planting_date": plant_date.strftime("%Y-%m-%d"),
        }
        for stage, offset in V_STAGE_OFFSETS.items():
            entry[stage] = (plant_date + timedelta(days=offset)).strftime("%Y-%m-%d")

        site_years.append(entry)

    return site_years


def export_metadata(site_years: list[dict]) -> Path:
    """Write site-year metadata (including V-stage dates) to CSV."""
    out = TMP_DIR / "site_year_metadata.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=site_years[0].keys())
        writer.writeheader()
        writer.writerows(site_years)
    print(f"Exported {len(site_years)} site-years → {out}")
    return out


def main() -> None:
    ensure_extracted(NEEDED_FILES)

    print("\nLoading planting dates...")
    site_years = load_site_years()

    print("\nSample site-years:")
    for sy in site_years[:3]:
        print(
            f"  Trial {sy['trial']:>3} | {sy['state']} - {sy['site']:<12} {sy['year']} "
            f"| Planted: {sy['planting_date']} | V6: {sy['V6']} → V10: {sy['V10']}"
        )

    export_metadata(site_years)


if __name__ == "__main__":
    main()
