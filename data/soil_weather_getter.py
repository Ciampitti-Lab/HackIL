"""
Extract soil and weather features from PRNT supplemental files for 2016 trials.

Soil features come from 4.SoilN.xlsx (sheet Nitrate-ammonium):
  1. PPNT (preplant) rows have no Plot_ID, so they are averaged to site-level
     and broadcast to all plots in the trial.
  2. PSNT (presidedress, ~V5-V6) rows have Plot_ID and are joined plot-level.
     PSNT reflects soil N before sidedress is applied; Side_N_SI captures how
     much N was added at sidedress (~V9), so both are included together.

Weather features come from 10.Weather.xlsx (sheet All_Weather), aggregated
over two growing windows using planting and V-stage dates from site_year_metadata.csv:
  - Pre-V6:  planting date → V6 (establishment + early vegetative)
  - V6-V10:  V6 → V10  (rapid growth window captured by Sentinel-2)

Output: data/processed/fusion/soil_weather_features.csv
  - One row per (trial, plot_id)
  - All numeric; NaN where PPNT or PSNT data was not collected for a trial/plot
"""

from pathlib import Path

import numpy as np
import pandas as pd

SOIL_FILE = Path("data/tmp/4.SoilN.xlsx")
WEATHER_FILE = Path("data/tmp/10.Weather.xlsx")
META_FILE = Path("data/tmp/site_year_metadata.csv")
NNI_FILE = Path("data/processed/nni/plot_nni.csv")
OUT_DIR = Path("data/processed/fusion")

GDD_BASE = 10.0     # base temperature for corn GDD (°C)
HEAT_THRESH = 35.0  # Tmax threshold for heat stress days (°C)


def to_num(series: pd.Series) -> pd.Series:
    """Convert a column that may contain '.' strings to float."""
    return pd.to_numeric(series, errors="coerce")


def compute_gdd(tmax: pd.Series, tmin: pd.Series) -> pd.Series:
    """Daily GDD with base GDD_BASE; negative values clipped to zero."""
    return ((tmax + tmin) / 2 - GDD_BASE).clip(lower=0)


def weather_window(wx: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Aggregate daily weather rows within [start, end) into feature dict."""
    mask = (wx["Date"] >= start) & (wx["Date"] < end)
    w = wx[mask].copy()
    if w.empty:
        return {k: np.nan for k in
                ["gdd", "precp_mm", "heat_days", "solar_mean_mjm2d"]}
    gdd = compute_gdd(w["Tmax"], w["Tmin"])
    return {
        "gdd":              round(gdd.sum(), 2),
        "precp_mm":         round(w["Precp"].sum(), 2),
        "heat_days":        int((w["Tmax"] > HEAT_THRESH).sum()),
        "solar_mean_mjm2d": round(w["SolarRad2"].mean(), 3),
    }


def extract_weather(meta: pd.DataFrame) -> pd.DataFrame:
    """Compute per-trial growing-season weather aggregates for 2016 trials."""
    wx_all = pd.read_excel(WEATHER_FILE, sheet_name="All_Weather")
    wx_all["Date"] = pd.to_datetime(wx_all["Date"])
    wx_all["Tmax"] = to_num(wx_all["Tmax"])
    wx_all["Tmin"] = to_num(wx_all["Tmin"])
    wx_all["Precp"] = to_num(wx_all["Precp"])
    wx_all["SolarRad2"] = to_num(wx_all["SolarRad2"])

    rows = []
    for _, row in meta.iterrows():
        trial = int(row["trial"])
        plant_dt = pd.to_datetime(row["planting_date"])
        v6_dt = pd.to_datetime(row["V6"])
        v10_dt = pd.to_datetime(row["V10"])

        wx = wx_all[wx_all["Trial#"] == trial]

        pre_v6 = weather_window(wx, plant_dt, v6_dt)
        v6_v10 = weather_window(wx, v6_dt, v10_dt)

        rows.append({
            "trial": trial,
            "gdd_plant_v6":       pre_v6["gdd"],
            "precp_plant_v6_mm":  pre_v6["precp_mm"],
            "gdd_v6_v10":         v6_v10["gdd"],
            "precp_v6_v10_mm":    v6_v10["precp_mm"],
            "heat_days_v6_v10":   v6_v10["heat_days"],
            "solar_v6_v10_mjm2d": v6_v10["solar_mean_mjm2d"],
        })

    return pd.DataFrame(rows)


def extract_soil(meta: pd.DataFrame) -> pd.DataFrame:
    """
    Extract soil nitrate features for 2016 from PPNT and PSNT samplings.

    PPNT rows → site-level averages (no Plot_ID in the data).
    PSNT rows → plot-level (joined by Plot_ID).
    Plant_N_SI and Side_N_SI (N rates) are taken from PSNT rows where available.
    """
    df = pd.read_excel(SOIL_FILE, sheet_name="Nitrate-ammonium")
    df = df[df["Year"] == 2016].copy()

    for col in ["Nitrate1", "Nitrate2", "Nitrate3", "Ammonium1",
                "Plant_N_SI", "Side_N_SI"]:
        df[col] = to_num(df[col])

    # Build (State, Site) -> trial mapping from metadata
    site_map = meta.set_index(["state", "site"])["trial"].to_dict()
    df["trial"] = df.apply(
        lambda r: site_map.get((r["State"], r["Site"]), np.nan), axis=1
    )
    df = df.dropna(subset=["trial"])
    df["trial"] = df["trial"].astype(int)

    # PPNT: site-level averages broadcast to all plots in trial
    ppnt = (
        df[df["Sam_Time"] == "PPNT"]
        .groupby("trial")[["Nitrate1", "Nitrate2", "Nitrate3", "Ammonium1"]]
        .mean()
        .rename(columns={
            "Nitrate1":  "no3_0_1ft_ppnt_ppm",
            "Nitrate2":  "no3_1_2ft_ppnt_ppm",
            "Nitrate3":  "no3_2_3ft_ppnt_ppm",
            "Ammonium1": "nh4_0_1ft_ppnt_ppm",
        })
        .reset_index()
    )

    # PSNT: plot-level
    psnt_raw = df[df["Sam_Time"] == "PSNT"].copy()
    psnt_raw["Plot_ID"] = to_num(psnt_raw["Plot_ID"])
    psnt = (
        psnt_raw
        .rename(columns={
            "Plot_ID":    "plot_id",
            "Nitrate1":   "no3_0_1ft_psnt_ppm",
            "Nitrate2":   "no3_1_2ft_psnt_ppm",
            "Ammonium1":  "nh4_0_1ft_psnt_ppm",
            "Plant_N_SI": "plant_n_kgha",
            "Side_N_SI":  "side_n_kgha",
        })
        [["trial", "plot_id",
          "no3_0_1ft_psnt_ppm", "no3_1_2ft_psnt_ppm", "nh4_0_1ft_psnt_ppm",
          "plant_n_kgha", "side_n_kgha"]]
        .dropna(subset=["plot_id"])
    )
    psnt["plot_id"] = psnt["plot_id"].astype(int)

    return ppnt, psnt


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    meta = pd.read_csv(META_FILE)
    meta_2016 = meta[meta["year"] == 2016].copy()

    print("Extracting weather features...")
    weather = extract_weather(meta_2016)
    print(f"  {len(weather)} trial-level weather rows")

    print("Extracting soil features...")
    ppnt, psnt = extract_soil(meta_2016)
    print(f"  PPNT: {len(ppnt)} trial rows  |  PSNT: {len(psnt)} plot rows")

    # Build a (trial, plot_id) frame covering all 2016 plots from NNI
    nni = pd.read_csv(NNI_FILE)[["trial", "plot_id"]].drop_duplicates()
    nni = nni[nni["trial"].isin(meta_2016["trial"])]

    # Join trial-level features (weather + PPNT) and plot-level (PSNT)
    out = nni.copy()
    out = out.merge(weather, on="trial", how="left")
    out = out.merge(ppnt,    on="trial", how="left")
    out = out.merge(psnt,    on=["trial", "plot_id"], how="left")

    out_path = OUT_DIR / "soil_weather_features.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved {len(out)} rows × {out.shape[1]} columns → {out_path}")
    print(f"Feature coverage (non-NaN %):")
    feat_cols = [c for c in out.columns if c not in ["trial", "plot_id"]]
    for c in feat_cols:
        pct = 100 * out[c].notna().mean()
        print(f"  {c:<30} {pct:.0f}%")


if __name__ == "__main__":
    main()
