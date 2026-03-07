"""
Compute per-plot Nitrogen Nutrition Index (NNI) from PRNT plant measurements.
Based on: https://www.sciencedirect.com/science/article/abs/pii/S0378429025002060

Formula (critical N dilution curve):
    n_critical = 3.49 * (biomass_Mgha ** -0.38)
    NNI = VT_TissN / n_critical

Where:
    VT_TissN: actual plant N concentration at VT stage (%)
    VTBdryY: above-ground dry biomass at VT stage (kg/ha, converted to Mg/ha)

Output: data/processed/nni/plot_nni.csv
Join key to S2 pixel data: (trial, plot_id)
"""

import csv
import zipfile
from pathlib import Path

import openpyxl

RAW_ZIP = Path("data/raw/doi_10_5061_dryad_66t1g1k2g__v20210803.zip")
TMP_DIR = Path("data/tmp")
OUT_DIR = Path("data/processed/nni")

NEEDED_FILE = "8.Yield_Plant_Measurements.xlsx"
S2_MIN_YEAR = 2016  # match the remote sensing filter

OUT_COLS = [
    "trial",
    "year",
    "state",
    "site",
    "plot_id",
    "block",
    "n_trt",
    "plant_n",
    "side_n",
    "vt_tiss_n",
    "vt_biomass_kgha",
    "nni",
]


def ensure_extracted() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out = TMP_DIR / NEEDED_FILE
    if out.exists():
        print(f"Already extracted: {out}")
        return
    print(f"Extracting {NEEDED_FILE} from {RAW_ZIP} ...")
    with zipfile.ZipFile(RAW_ZIP) as zf:
        zf.extract(NEEDED_FILE, TMP_DIR)
    print("Done.")


def compute_nni(vt_tiss_n: float, vt_biomass_kgha: float) -> float:
    """NNI from critical N dilution curve (biomass must be in Mg/ha)."""
    biomass_mgha = vt_biomass_kgha / 1000.0
    n_critical = 3.49 * (biomass_mgha**-0.38)
    return vt_tiss_n / n_critical


def load_nni() -> list[dict]:
    wb = openpyxl.load_workbook(TMP_DIR / NEEDED_FILE, read_only=True)
    ws = wb["All_Plant"]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    col = {h: i for i, h in enumerate(headers)}

    results = []
    skipped_year = skipped_missing = 0

    for row in rows[1:]:
        trial = row[col["Trial#"]]
        if trial is None:
            continue

        year = row[col["Year"]]
        if not year or year < S2_MIN_YEAR:
            skipped_year += 1
            continue

        vt_tiss_n = row[col["VT_TissN"]]
        vt_biomass = row[col["VTBdryY"]]

        if (
            vt_tiss_n == "."
            or vt_biomass == "."
            or vt_tiss_n is None
            or vt_biomass is None
        ):
            skipped_missing += 1
            continue

        try:
            vt_tiss_n = float(vt_tiss_n)
            vt_biomass = float(vt_biomass)
        except (ValueError, TypeError):
            skipped_missing += 1
            continue

        if vt_biomass <= 0:
            skipped_missing += 1
            continue

        nni = compute_nni(vt_tiss_n, vt_biomass)

        results.append(
            {
                "trial": int(trial),
                "year": int(year),
                "state": row[col["State"]],
                "site": row[col["Site"]],
                "plot_id": int(row[col["Plot_ID"]]),
                "block": row[col["Block"]],
                "n_trt": row[col["N_Trt"]],
                "plant_n": row[col["Plant_N"]],
                "side_n": row[col["Side_N"]],
                "vt_tiss_n": round(vt_tiss_n, 4),
                "vt_biomass_kgha": round(vt_biomass, 2),
                "nni": round(nni, 4),
            }
        )

    print(
        f"  Skipped {skipped_year} rows (year < {S2_MIN_YEAR}), "
        f"{skipped_missing} rows (missing VT_TissN or VTBdryY)"
    )
    return results


def main() -> None:
    ensure_extracted()

    print("\nComputing NNI per plot...")
    records = load_nni()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "plot_nni.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLS)
        writer.writeheader()
        writer.writerows(records)

    print(f"Exported {len(records)} plot NNI values → {out_path}")

    # Summary
    nni_values = [r["nni"] for r in records]
    if nni_values:
        print(f"  NNI range: {min(nni_values):.3f} – {max(nni_values):.3f}")
        print(f"  NNI mean:  {sum(nni_values)/len(nni_values):.3f}")
        deficient = sum(1 for v in nni_values if v < 1.0)
        print(
            f"  N-deficient plots (NNI < 1): {deficient}/{len(nni_values)} "
            f"({100*deficient/len(nni_values):.1f}%)"
        )


if __name__ == "__main__":
    main()
