"""Compare CRH (Currently Rated Helpful) note counts across ablation runs vs a baseline.

Usage:
  python ablation/verify_ablation.py \
    --baseline sourcecode/data_small/scored_notes.tsv \
    --runs-dir sourcecode/ablation_runs_small/runs

Reads finalRatingStatus from each run's scored_notes.tsv, prints a per-run summary
(notes / CRH / overlap with baseline) and pairwise Jaccard overlap between runs.
"""

import argparse
from pathlib import Path
import pandas as pd


CRH = "CURRENTLY_RATED_HELPFUL"


def load_crh(path):
  df = pd.read_csv(
    path,
    sep="\t",
    usecols=["noteId", "finalRatingStatus"],
    dtype={"noteId": str, "finalRatingStatus": str},
    low_memory=False,
  )
  return set(df.loc[df["finalRatingStatus"] == CRH, "noteId"]), len(df)


def main():
  p = argparse.ArgumentParser()
  p.add_argument("--baseline", required=True, help="path to original scored_notes.tsv")
  p.add_argument("--runs-dir", required=True, help="dir with one subdir per run, each containing scored_notes.tsv")
  args = p.parse_args()

  base_crh, base_total = load_crh(args.baseline)
  print(f"baseline:        {base_total:>10} notes  {len(base_crh):>9} CRH ({100*len(base_crh)/base_total:>5.2f}%)")

  runs = {}
  for d in sorted(Path(args.runs_dir).iterdir()):
    sn = d / "scored_notes.tsv"
    if d.is_dir() and sn.exists():
      runs[d.name] = load_crh(sn)

  print()
  print(f"{'run':<32}{'notes':>11}{'CRH':>10}{'CRH%':>8}{'overlap':>10}{'lost':>9}{'new':>8}")
  for name, (crh, total) in runs.items():
    overlap = len(crh & base_crh)
    lost = len(base_crh - crh)
    new = len(crh - base_crh)
    pct = 100 * len(crh) / total if total else 0
    print(f"{name:<32}{total:>11}{len(crh):>10}{pct:>7.2f}%{overlap:>10}{lost:>9}{new:>8}")

  if len(runs) > 1:
    print("\npairwise CRH Jaccard (|A ∩ B| / |A ∪ B|):")
    names = list(runs)
    for i, a in enumerate(names):
      for b in names[i + 1 :]:
        ca, _ = runs[a]
        cb, _ = runs[b]
        u = ca | cb
        j = len(ca & cb) / len(u) if u else 0
        print(f"  {a} ↔ {b}: {j:.4f}")


if __name__ == "__main__":
  main()
