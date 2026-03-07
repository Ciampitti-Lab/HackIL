"""
Precompute all dashboard predictions and persist them as GeoJSON.

Generates one GeoJSON file per trial site, with plot polygon geometries and
embedded predictions for every (n_stages, model_type) combination:
  - n_stages: 1 to 5  (V6 only → all 5 stages)
  - model_type: "remote" (RS-only), "fusion" (RS + soil/weather)

All 7 × 5 × 2 = 70 combinations are stored in each feature's properties so
the frontend can switch scenarios client-side without any further API calls.

Output: data/processed/predictions/trial_{id}.geojson  (one per trial)
These files are committed to the repo and baked into the Docker image.

Honesty note: predictions are made on all plots in the training dataset,
including those used for model training. These are demo predictions on known
data and should not be interpreted as out-of-sample performance. For actual perfomance
metrics, see the evaluation plots and metrics in the README, which are based on held-out test sets.
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
RS_MODEL_PKL = ROOT / "models/remote_sensing/LogisticRegression_clf.pkl"
FUSION_MODEL_PKL = ROOT / "models/fusion/LogisticRegression_clf.pkl"
RS_DATASET = ROOT / "data/processed/training_dataset_filtered.csv"
FUSION_DATASET = ROOT / "data/processed/training_dataset_fusion.csv"
GEOJSON_DIR = ROOT / "data/processed/remote_sensing"
OUT_DIR = ROOT / "data/processed/predictions"

STAGES = ["V6", "V7", "V8", "V9", "V10"]


def load_models():
    with open(RS_MODEL_PKL, "rb") as f:
        rs = pickle.load(f)
    with open(FUSION_MODEL_PKL, "rb") as f:
        fu = pickle.load(f)
    return rs, fu


def stage_cols(feat_cols: list[str], stage: str) -> list[str]:
    return [c for c in feat_cols if c.endswith(f"_{stage}")]


def impute_stages(
    X: pd.DataFrame, feat_cols: list[str], col_means: pd.Series, n_stages: int
) -> np.ndarray:
    """Zero-out stages beyond n_stages with training-set column means."""
    X_sim = X[feat_cols].copy()
    for s in STAGES[n_stages:]:
        cols = stage_cols(feat_cols, s)
        X_sim[cols] = col_means[cols].values
    return X_sim.values


def load_datasets():
    rs_df = pd.read_csv(RS_DATASET)
    fu_df = pd.read_csv(FUSION_DATASET)
    return rs_df, fu_df


def load_geometries(trial: int) -> dict[int, dict]:
    """Return {plot_id: geojson_geometry} from the S2 geojson for this trial."""
    candidates = list(GEOJSON_DIR.glob(f"s2_trial{trial}_*.geojson"))
    if not candidates:
        raise FileNotFoundError(f"No S2 geojson found for trial {trial}")
    with open(candidates[0]) as f:
        gj = json.load(f)
    # Take geometry from the V6 row for each plot (all stages share the same boundary)
    geoms = {}
    for feat in gj["features"]:
        props = feat["properties"]
        if props.get("stage") == "V6":
            pid = int(props["plot_id"])
            geoms[pid] = feat["geometry"]
    return geoms


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading models...")
    rs_art, fu_art = load_models()

    print("Loading datasets...")
    rs_df, fu_df = load_datasets()

    # Merge fusion soil/weather NaN -> fill with fusion model's col_means
    # (same imputation used at training time)
    fu_col_means = fu_art["col_means"]

    trials = sorted(rs_df["trial"].unique())
    print(f"Trials to process: {trials}\n")

    for trial in trials:
        print(f"  Trial {trial}...", end=" ", flush=True)

        # Subset both datasets to this trial
        rs_t = rs_df[rs_df["trial"] == trial].copy()
        fu_t = fu_df[fu_df["trial"] == trial].copy()

        # Load plot geometries
        try:
            geoms = load_geometries(trial)
        except FileNotFoundError as e:
            print(f"SKIP ({e})")
            continue

        # Ground truth: use plant_n_kgha / side_n_kgha (SI, kg/ha) from fusion dataset
        # `plant_n` / `side_n` in rs_t are in lbs/acre from the shapefile
        gt = rs_t.set_index("plot_id")[
            ["nni", "n_trt", "block", "plant_n", "side_n"]
        ].copy()
        # Pull SI columns from fusion dataset and attach to gt
        fu_si = fu_t.set_index("plot_id")[["plant_n_kgha", "side_n_kgha"]]
        gt = gt.join(fu_si, how="left")
        gt["is_deficient"] = (gt["nni"] < 1.0).astype(int)

        # Fill fusion SW NaN with training-set col_means
        fu_t_filled = fu_t.copy()
        for col in fu_art["sw_feat_cols"]:
            if col in fu_t_filled.columns:
                fu_t_filled[col] = fu_t_filled[col].fillna(fu_col_means[col])

        # RS feature matrix (fill any NaN RS cols with RS col_means)
        rs_feat_cols = rs_art["feat_cols"]
        rs_col_means = rs_art["col_means"]
        X_rs = rs_t.set_index("plot_id")[rs_feat_cols].fillna(rs_col_means)

        # Fusion feature matrix
        fu_feat_cols = fu_art["feat_cols"]
        fu_rs_feat_cols = fu_art["rs_feat_cols"]
        X_fu = fu_t_filled.set_index("plot_id")[fu_feat_cols].fillna(fu_col_means)

        # Build predictions for all combos
        predictions: dict[int, dict] = {pid: {} for pid in gt.index}

        for n in range(1, 6):
            # RS-only
            X_sim = impute_stages(X_rs, rs_feat_cols, rs_col_means, n)
            X_sim_sc = rs_art["scaler"].transform(X_sim)
            proba_rs = rs_art["model"].predict_proba(X_sim_sc)[:, 1]
            pred_rs = (proba_rs >= rs_art["threshold"]).astype(int)
            for i, pid in enumerate(X_rs.index):
                predictions[pid][f"remote_{n}_prob"] = round(float(proba_rs[i]), 4)
                predictions[pid][f"remote_{n}_pred"] = int(pred_rs[i])

            # Fusion
            X_sim_fu = impute_stages(X_fu, fu_rs_feat_cols, fu_col_means, n)
            # Reconstruct full feature array: imputed RS + SW columns
            sw_vals = X_fu[fu_art["sw_feat_cols"]].values
            X_sim_fu_full = np.hstack([X_sim_fu, sw_vals])
            X_sim_fu_sc = fu_art["scaler"].transform(X_sim_fu_full)
            proba_fu = fu_art["model"].predict_proba(X_sim_fu_sc)[:, 1]
            pred_fu = (proba_fu >= fu_art["threshold"]).astype(int)
            for i, pid in enumerate(X_fu.index):
                predictions[pid][f"fusion_{n}_prob"] = round(float(proba_fu[i]), 4)
                predictions[pid][f"fusion_{n}_pred"] = int(pred_fu[i])

        features = []
        for pid, row in gt.iterrows():
            if pid not in geoms:
                continue  # plot has no S2 geometry
            props = {
                "plot_id": int(pid),
                "n_trt": int(row["n_trt"]),
                "block": int(row["block"]),
                "plant_n_kgha": round(float(row["plant_n_kgha"]), 2) if pd.notna(row.get("plant_n_kgha")) else round(float(row["plant_n"]) * 1.12085, 2),
                "side_n_kgha": round(float(row["side_n_kgha"]), 2) if pd.notna(row.get("side_n_kgha")) else round(float(row["side_n"]) * 1.12085, 2),
                "nni": round(float(row["nni"]), 4),
                "is_deficient": int(row["is_deficient"]),
                **predictions.get(pid, {}),
            }
            features.append(
                {
                    "type": "Feature",
                    "geometry": geoms[pid],
                    "properties": props,
                }
            )

        site_name = rs_t["site"].iloc[0] if "site" in rs_t.columns else str(trial)
        state_name = rs_t["state"].iloc[0] if "state" in rs_t.columns else ""
        out = {
            "type": "FeatureCollection",
            "trial": int(trial),
            "site": site_name,
            "state": state_name,
            "features": features,
        }

        out_path = OUT_DIR / f"trial_{trial}.geojson"
        with open(out_path, "w") as f:
            json.dump(out, f, separators=(",", ":"))
        print(f"{len(features)} plots → {out_path.name}")

    print(f"\nDone. {len(trials)} files written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
