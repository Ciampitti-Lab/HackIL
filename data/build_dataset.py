"""
Build the model training dataset by:
  1. Loading plot-level S2 zonal means from data/processed/remote_sensing/*.geojson
  2. Pivoting stages to wide format (NDVI_V6, NDVI_V7, ... NDVI_V10, ...)
  3. Joining with plot NNI labels from data/processed/nni/plot_nni.csv

Output: data/processed/training_dataset.csv
  - One row per plot
  - Feature columns: {index}_{stage} for each spectral index × V-stage
  - Target column: nni
"""

import json
from pathlib import Path

import pandas as pd

S2_DIR = Path("data/processed/remote_sensing")
NNI_CSV = Path("data/processed/nni/plot_nni.csv")
OUT_PATH = Path("data/processed/training_dataset.csv")

INDEX_COLS = [
    "NDVI",
    "GNDVI",
    "NDRE",
    "EVI2",
    "CIrededge",
    "NIRv",
    "SAVI",
    "OSAVI",
    "TGI",
    "MCARI",
    "OCARI",
]
BAND_COLS = ["blue_B02", "green_B03", "red_B04", "rededge_B05", "nir_B08"]
FEATURE_COLS = INDEX_COLS + BAND_COLS

META_COLS = [
    "trial",
    "site",
    "state",
    "year",
    "plot_id",
    "block",
    "n_trt",
    "plant_n",
    "side_n",
]


def load_pixels() -> pd.DataFrame:
    """Read all GeoJSON files and return a flat DataFrame of plot-stage properties."""
    geojsons = sorted(S2_DIR.glob("*.geojson"))
    if not geojsons:
        raise FileNotFoundError(f"No GeoJSON files found in {S2_DIR}")

    frames = []
    for path in geojsons:
        with open(path) as f:
            gj = json.load(f)
        props = [feat["properties"] for feat in gj["features"]]
        if props:
            frames.append(pd.DataFrame(props))
        print(f"  {path.name}: {len(props)} rows")

    return pd.concat(frames, ignore_index=True)


def pivot_stages_wide(agg: pd.DataFrame) -> pd.DataFrame:
    """Pivot stage rows to columns: NDVI_V6, NDVI_V7, ..."""
    # Plots on S2 tile boundaries can appear twice in reduceRegions output.
    # Average any duplicate (trial, plot_id, stage) rows before pivoting.
    dup_mask = agg.duplicated(subset=["trial", "plot_id", "stage"], keep=False)
    if dup_mask.any():
        n_dups = dup_mask.sum()
        print(
            f"  Deduplicating {n_dups} rows with duplicate (trial, plot_id, stage) — averaging values"
        )
        agg = agg.groupby(["trial", "plot_id", "stage"], as_index=False)[
            FEATURE_COLS
        ].mean()

    wide = agg.pivot(index=["trial", "plot_id"],
                     columns="stage", values=FEATURE_COLS)
    # Flatten MultiIndex columns: (NDVI, V6) → NDVI_V6
    wide.columns = [f"{feat}_{stage}" for feat, stage in wide.columns]
    return wide.reset_index()


def add_plot_metadata(wide: pd.DataFrame, pixels: pd.DataFrame) -> pd.DataFrame:
    """Re-attach plot-level metadata (constant across stages for each plot)."""
    meta = pixels[META_COLS].drop_duplicates(subset=["trial", "plot_id"])
    return wide.merge(meta, on=["trial", "plot_id"], how="left")


def main() -> None:
    print(f"Loading S2 plot-level data from {S2_DIR}/")
    pixels = load_pixels()
    print(
        f"  Total rows: {len(pixels):,}  |  trials: {pixels['trial'].nunique()}  |  plots: {pixels['plot_id'].nunique()}"
    )

    print("Pivoting stages to wide format...")
    wide = pivot_stages_wide(pixels)
    wide = add_plot_metadata(wide, pixels)

    print(f"\nLoading NNI labels from {NNI_CSV}")
    nni = pd.read_csv(NNI_CSV)[
        ["trial", "plot_id", "nni", "vt_tiss_n", "vt_biomass_kgha"]
    ]

    print("Joining S2 features with NNI labels...")
    dataset = wide.merge(nni, on=["trial", "plot_id"], how="inner")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUT_PATH, index=False)

    feat_cols = [
        c for c in dataset.columns if any(c.startswith(f) for f in FEATURE_COLS)
    ]
    print(f"\nDataset saved → {OUT_PATH}")
    print(f"  Rows (plots):     {len(dataset)}")
    print(
        f"  Feature columns:  {len(feat_cols)}  ({len(FEATURE_COLS)} indices × up to 5 stages)"
    )
    print(
        f"  NNI range:        {dataset['nni'].min():.3f} – {dataset['nni'].max():.3f}"
    )
    print(
        f"  N-deficient (NNI < 1): {(dataset['nni'] < 1).sum()}/{len(dataset)} ({100*(dataset['nni'] < 1).mean():.1f}%)"
    )


if __name__ == "__main__":
    main()
