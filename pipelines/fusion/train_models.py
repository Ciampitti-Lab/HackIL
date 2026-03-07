"""
Train a fusion binary classifier to flag N-deficient maize plots (NNI < 1.0)
from Sentinel-2 spectral features combined with soil and weather covariates.

Fusion strategy:
  - RS features (80 columns): Sentinel-2 spectral indices across up to 5 V-stages.
  - Soil/weather features (15 columns): PPNT/PSNT soil nitrate, N rates, and
    growing-season weather aggregates from the PRNT dataset.
  - At inference, the scouting tool routes to this model when soil/weather inputs
    are available, and falls back to the RS-only model otherwise.

Stage-dropout augmentation is applied only to RS stage columns:
  1. For each training plot, DROPOUT_COPIES extra rows are generated.
  2. Each copy has a random subset of RS stages replaced by training-set column means.
  3. Soil/weather columns are never dropped — they are plot/site constants.
  4. NaN soil/weather values (plots without PSNT sampling) are filled with
     training-set column means before fitting, same imputation as RS dropout.

Models: Logistic Regression, Random Forest, XGBoost (CUDA), LightGBM
Split:  80/20 stratified random split (seed=42)
Target: N-deficient flag derived from NNI < 1.0

Outputs:
  models/fusion/<name>_clf.pkl          - best model, scaler, col_means, threshold
  out/fusion/results.csv                - per-model metrics (all 5 stages)
  out/fusion/stage_curve.png            - AUC and F1 vs. number of RS stages available
  out/fusion/train_col_means.csv        - column means for inference imputation

Usage:
    uv run python pipelines/fusion/train_models.py
"""

import pickle
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

DATASET = Path("data/processed/training_dataset_fusion.csv")
MODELS_DIR = Path("models/fusion")
OUT_DIR = Path("out/fusion")

STAGES = ["V6", "V7", "V8", "V9", "V10"]
RS_FEATURE_PREFIX = [
    "NDVI", "GNDVI", "NDRE", "EVI2", "CIrededge",
    "NIRv", "SAVI", "OSAVI", "TGI", "MCARI", "OCARI",
    "blue_B02", "green_B03", "red_B04", "rededge_B05", "nir_B08",
]
SW_FEATURE_COLS = [
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
RANDOM_STATE = 42
DROPOUT_COPIES = 5   # augmented stage-dropout copies per plot per training pass
POS_WEIGHT = (1 - 0.246) / 0.246   # ~3.1 for XGBoost, based on filtered fusion class ratio


def load_data() -> tuple[pd.DataFrame, pd.Series, list[str], list[str]]:
    """
    Load the fusion dataset and return feature matrices and column name lists.

    RS columns with NaN (plot on tile boundary, stage not imaged) are filled with
    their column means. Soil/weather NaN values are filled separately so that
    column means are computed only on the training split (see main()).
    Returns: X (all features, NaN SW preserved), y, rs_feat_cols, sw_feat_cols.
    """
    df = pd.read_csv(DATASET)
    rs_feat_cols = [c for c in df.columns if any(c.startswith(p) for p in RS_FEATURE_PREFIX)]
    sw_feat_cols = [c for c in SW_FEATURE_COLS if c in df.columns]

    feat_cols = rs_feat_cols + sw_feat_cols
    X = df[feat_cols].copy()
    # RS NaN filled globally (missing stage = no observation, use dataset mean)
    X[rs_feat_cols] = X[rs_feat_cols].fillna(X[rs_feat_cols].mean())
    # SW NaN kept here — filled with training-set means after split (in main)
    y = (df["nni"] < 1.0).astype(int)

    print(f"  RS features:           {len(rs_feat_cols)}")
    print(f"  Soil/weather features: {len(sw_feat_cols)}")
    print(f"  Total features:        {len(feat_cols)}  |  Plots: {len(X)}")
    print(f"  N-deficient: {y.sum()}/{len(y)} ({100*y.mean():.1f}%)")
    return X, y, rs_feat_cols, sw_feat_cols


def stage_cols(rs_feat_cols: list[str], stage: str) -> list[str]:
    return [c for c in rs_feat_cols if c.endswith(f"_{stage}")]


def dropout_augment(
    X: pd.DataFrame,
    y: pd.Series,
    rs_feat_cols: list[str],
    col_means: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Augment the training set with stage-dropout copies of each plot.

    Only RS stage columns are dropped; soil/weather columns are never zeroed
    out because they are site/plot constants, not time-series observations.
    Each copy has a random number of RS stages (1 to len(STAGES)-1) replaced
    by training-set column means. The original row is always included.
    Returns plain numpy arrays for efficiency.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    X_np = X.values.copy()
    y_np = y.values

    all_cols = list(X.columns)
    stage_idx = {
        s: [all_cols.index(c) for c in stage_cols(rs_feat_cols, s)]
        for s in STAGES
    }
    means_np = col_means.values

    aug_X = [X_np]
    aug_y = [y_np]

    for _ in range(DROPOUT_COPIES):
        X_copy = X_np.copy()
        n_drop = rng.integers(1, len(STAGES), size=len(X_np))
        for i in range(len(X_np)):
            dropped = rng.choice(STAGES, size=n_drop[i], replace=False)
            for s in dropped:
                for col_i in stage_idx[s]:
                    X_copy[i, col_i] = means_np[col_i]
        aug_X.append(X_copy)
        aug_y.append(y_np)

    return np.vstack(aug_X), np.concatenate(aug_y)


def simulate_stages(
    X: pd.DataFrame,
    rs_feat_cols: list[str],
    col_means: pd.Series,
    n_stages: int,
) -> np.ndarray:
    """
    Simulate having only the first n_stages RS stages available.

    Columns for the remaining RS stages are replaced with training-set column means.
    Soil/weather columns are left unchanged — they are always assumed available
    when routing to the fusion model.
    """
    X_sim = X.copy()
    for s in STAGES[n_stages:]:
        cols = stage_cols(rs_feat_cols, s)
        X_sim[cols] = col_means[cols].values
    return X_sim.values


def best_threshold_metrics(model, X_test, y_test, threshold: float | None = None) -> dict:
    """
    Evaluate a classifier on X_test/y_test at a fixed decision threshold.

    If threshold is None, the F1-optimal threshold is derived from y_test itself;
    only use that path when calling on training/validation data, not the test set.
    """
    proba = model.predict_proba(X_test)[:, 1]
    if threshold is None:
        precisions, recalls, thresholds = precision_recall_curve(y_test, proba)
        f1s = 2 * precisions * recalls / (precisions + recalls + 1e-9)
        threshold = float(thresholds[np.argmax(f1s[:-1])]) if len(thresholds) else 0.5
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    return {
        "Threshold": round(threshold, 3),
        "AUC":       round(roc_auc_score(y_test, proba), 4),
        "F1":        round(f1_score(y_test, pred, zero_division=0), 4),
        "Recall":    round(recall_score(y_test, pred, zero_division=0), 4),
        "Specif":    round(tn / (tn + fp), 4),
        "Accuracy":  round(accuracy_score(y_test, pred), 4),
    }


def find_threshold(model, X_train, y_train, beta: float = 2.0) -> float:
    """
    Find the decision threshold that maximises F-beta on training-set predictions.

    beta=2 weights recall twice as much as precision, reflecting the scouting
    priority: missing a deficient field (false negative) is more costly than
    a wasted scout visit (false positive).
    This threshold is stored and applied fixed to the test set to avoid leakage.
    """
    proba = model.predict_proba(X_train)[:, 1]
    precisions, recalls, thresholds = precision_recall_curve(y_train, proba)
    b2 = beta ** 2
    fbeta = (1 + b2) * precisions * recalls / (b2 * precisions + recalls + 1e-9)
    return float(thresholds[np.argmax(fbeta[:-1])]) if len(thresholds) else 0.5


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading fusion dataset from {DATASET}")
    print("XGBoost: CUDA GPU  |  LightGBM / RF / LogReg: CPU")
    X, y, rs_feat_cols, sw_feat_cols = load_data()
    feat_cols = rs_feat_cols + sw_feat_cols

    X_train_df, X_test_df, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    print(f"\n  Train: {len(X_train_df)}  |  Test: {len(X_test_df)}")

    # Fill soil/weather NaN with training-set means to avoid test leakage.
    col_means = X_train_df.mean()
    X_train_df = X_train_df.fillna(col_means)
    X_test_df = X_test_df.fillna(col_means)
    col_means.to_csv(OUT_DIR / "train_col_means.csv")

    print(f"\nAugmenting with RS stage dropout ({DROPOUT_COPIES} copies x {len(X_train_df)} plots)...")
    X_aug, y_aug = dropout_augment(X_train_df, y_train, rs_feat_cols, col_means)
    print(f"  Augmented train size: {len(X_aug):,} rows")

    scaler = StandardScaler()
    X_aug_sc = scaler.fit_transform(X_aug)
    X_test_np = X_test_df.values
    X_test_sc = scaler.transform(X_test_np)

    # Train each classifier, find the F1-optimal threshold on training preds,
    # and apply it fixed to the test set.
    print("\nFusion classification with stage-dropout training (all 5 RS stages on test):")
    clf_defs = {
        "LogisticRegression": (
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE),
            True,
        ),
        "RandomForest": (
            RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=RANDOM_STATE),
            False,
        ),
        "XGBoost": (
            XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=5,
                          subsample=0.8, colsample_bytree=0.8, scale_pos_weight=POS_WEIGHT,
                          device="cuda", verbosity=0, eval_metric="logloss",
                          random_state=RANDOM_STATE),
            False,
        ),
        "LightGBM": (
            LGBMClassifier(n_estimators=300, learning_rate=0.05, max_depth=5,
                           subsample=0.8, colsample_bytree=0.8, class_weight="balanced",
                           random_state=RANDOM_STATE, verbose=-1),
            False,
        ),
    }

    results = []
    fitted = {}   # name -> (model, scaled, threshold)
    best_recall, best_name = -np.inf, None

    for name, (model, scaled) in clf_defs.items():
        Xtr = X_aug_sc if scaled else X_aug
        Xte = X_test_sc if scaled else X_test_np
        model.fit(Xtr, y_aug)
        # F-beta (β=2) threshold found on training predictions only, applied fixed here.
        thresh = find_threshold(model, Xtr, y_aug)
        m = best_threshold_metrics(model, Xte, y_test, threshold=thresh)
        results.append({"model": name, **m})
        fitted[name] = (model, scaled, thresh)
        print(f"  {name:<20}  AUC={m['AUC']:.4f}  F1={m['F1']:.4f}  "
              f"Recall={m['Recall']:.4f}  Specif={m['Specif']:.4f}  (thresh={m['Threshold']})")
        if m["Recall"] > best_recall:
            best_recall, best_name = m["Recall"], name

    best_model, best_scaled, best_thresh = fitted[best_name]
    print(f"\n  Best model: {best_name} (Recall={best_recall:.4f}, thresh={best_thresh:.3f})")
    with open(MODELS_DIR / f"{best_name}_clf.pkl", "wb") as f:
        pickle.dump({
            "model":        best_model,
            "scaler":       scaler,
            "col_means":    col_means,
            "feat_cols":    feat_cols,
            "rs_feat_cols": rs_feat_cols,
            "sw_feat_cols": sw_feat_cols,
            "stages":       STAGES,
            "threshold":    best_thresh,
        }, f)

    pd.DataFrame(results).to_csv(OUT_DIR / "results.csv", index=False)

    # Stage-availability curve: evaluate best-threshold performance with 1 to 5 RS stages.
    # Soil/weather features are always present (that is the assumption for the fusion model).
    print("\nStage-availability curve (1 to 5 RS stages on test set, soil/weather always present):")
    curve = {name: {"AUC": [], "F1": []} for name in clf_defs}

    for n in range(1, len(STAGES) + 1):
        X_sim_np = simulate_stages(X_test_df, rs_feat_cols, col_means, n)
        X_sim_sc = scaler.transform(X_sim_np)
        label = "+".join(STAGES[:n])
        row_parts = []
        for name, (model, scaled, thresh) in fitted.items():
            Xte = X_sim_sc if scaled else X_sim_np
            # Apply the fixed training-set threshold to avoid test leakage.
            m = best_threshold_metrics(model, Xte, y_test, threshold=thresh)
            curve[name]["AUC"].append(m["AUC"])
            curve[name]["F1"].append(m["F1"])
            row_parts.append(f"{name} AUC={m['AUC']:.3f} F1={m['F1']:.3f}")
        print(f"  {n} [{label}]:  " + "  |  ".join(row_parts))

    # Plot
    colors = {"LogisticRegression": "#2196F3", "RandomForest": "#4CAF50",
               "XGBoost": "#FF5722", "LightGBM": "#9C27B0"}
    x = list(range(1, len(STAGES) + 1))
    x_labels = ["+".join(STAGES[:n]) for n in x]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for name in clf_defs:
        ax1.plot(x, curve[name]["AUC"], marker="o", label=name, color=colors[name])
        ax2.plot(x, curve[name]["F1"],  marker="o", label=name, color=colors[name])

    for ax, metric in [(ax1, "AUC (ROC)"), (ax2, "F1 score")]:
        ax.set_xlabel("RS stages available at inference")
        ax.set_ylabel(metric)
        ax.set_title(f"{metric} vs. RS stages available")
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=20, ha="right")
        ax.legend(fontsize=8)
        ax.set_ylim(0, 1)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Fusion classifier (RS + soil/weather): stage-dropout training\n"
        "AUC & F1 vs. RS stages available at inference (soil/weather always present)",
        fontsize=11,
    )
    fig.tight_layout()
    plot_path = OUT_DIR / "stage_curve.png"
    fig.savefig(plot_path, dpi=150)
    print(f"\nStage curve -> {plot_path}")


if __name__ == "__main__":
    main()
