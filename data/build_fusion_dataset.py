"""
Build the fusion model training dataset by joining:
  1. data/processed/training_dataset_filtered.csv  (RS-only features + NNI labels)
  2. data/processed/fusion/soil_weather_features.csv  (soil + weather features)

The join key is (trial, plot_id). Soil and weather columns with low coverage
are retained; the fusion model uses only whatever is available per plot.
Plots missing all soil features still have full weather coverage.

Output: data/processed/training_dataset_fusion.csv
  - One row per plot (same 448 plots as the filtered RS dataset)
  - Columns: all RS feature columns + 15 soil/weather features + NNI target
"""

from pathlib import Path

import pandas as pd

RS_DATASET = Path("data/processed/training_dataset_filtered.csv")
SW_FEATURES = Path("data/processed/fusion/soil_weather_features.csv")
OUT_PATH = Path("data/processed/training_dataset_fusion.csv")

SOIL_WEATHER_COLS = [
    "gdd_plant_v6",
    "precp_plant_v6_mm",
    "gdd_v6_v10",
    "precp_v6_v10_mm",
    "heat_days_v6_v10",
    "solar_v6_v10_mjm2d",
    "no3_0_1ft_ppnt_ppm",
    "no3_1_2ft_ppnt_ppm",
    "no3_2_3ft_ppnt_ppm",
    "nh4_0_1ft_ppnt_ppm",
    "no3_0_1ft_psnt_ppm",
    "no3_1_2ft_psnt_ppm",
    "nh4_0_1ft_psnt_ppm",
    "plant_n_kgha",
    "side_n_kgha",
]


def main() -> None:
    rs = pd.read_csv(RS_DATASET)
    sw = pd.read_csv(SW_FEATURES)[["trial", "plot_id"] + SOIL_WEATHER_COLS]

    print(f"RS dataset:            {len(rs)} plots, {rs.shape[1]} columns")
    print(f"Soil/weather features: {len(sw)} rows, {len(SOIL_WEATHER_COLS)} feature columns")

    out = rs.merge(sw, on=["trial", "plot_id"], how="left")

    print(f"\nFusion dataset:        {len(out)} plots, {out.shape[1]} columns")
    print("\nSoil/weather feature coverage in filtered trials:")
    for col in SOIL_WEATHER_COLS:
        pct = 100 * out[col].notna().mean()
        print(f"  {col:<30} {pct:.0f}%")

    out.to_csv(OUT_PATH, index=False)
    print(f"\nSaved → {OUT_PATH}")


if __name__ == "__main__":
    main()
