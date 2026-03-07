"""
Filter the training dataset to exclude trials where NNI is unreliable.

Trials 44, 45, 47, 49 are excluded based on the paper's notes that NNI
does not perform well at these sites.
"""

from pathlib import Path
import pandas as pd

IN_PATH = Path("data/processed/training_dataset.csv")
OUT_PATH = Path("data/processed/training_dataset_filtered.csv")

EXCLUDE_TRIALS = {44, 45, 47, 49}

df = pd.read_csv(IN_PATH)
print(f"Before: {len(df)} plots, {df['trial'].nunique()} trials")

df_filtered = df[~df["trial"].isin(EXCLUDE_TRIALS)].copy()
print(f"After:  {len(df_filtered)} plots, {df_filtered['trial'].nunique()} trials")
print(f"Trials kept: {sorted(df_filtered['trial'].unique().tolist())}")
print(f"N-deficient: {(df_filtered['nni'] < 1).sum()}/{len(df_filtered)} ({100*(df_filtered['nni'] < 1).mean():.1f}%)")

df_filtered.to_csv(OUT_PATH, index=False)
print(f"\nSaved → {OUT_PATH}")
