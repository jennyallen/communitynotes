"""Generate participant-ID files + manifest for the rater/writer ablation grid.

Reads prescoring rater output, ranks raters by |internalRaterFactor1| within a chosen
scorer (default MFCoreScorer), and writes:

  {out_dir}/ids/{strategy}_{pct}pct_seed{seed}.txt   one participant ID per line
  {out_dir}/manifest.tsv                              array_idx -> ablation row

The manifest is consumed by run_ablation.sbatch via $SLURM_ARRAY_TASK_ID.
"""

import argparse
import math
import os

import numpy as np
import pandas as pd


STRATEGIES = ("extreme", "central", "random")


def parse_args():
  p = argparse.ArgumentParser()
  p.add_argument("--prescoring-rater-output", required=True)
  p.add_argument("--scorer-name", default="MFCoreScorer")
  p.add_argument("--strategies", default=",".join(STRATEGIES))
  p.add_argument("--percents", required=True, help="CSV floats, e.g. 10,25,50")
  p.add_argument("--reps", type=int, default=5, help="random replicates; deterministic strategies always emit 1 entry per pct")
  p.add_argument("--base-seed", type=int, default=0)
  p.add_argument("--out-dir", required=True)
  p.add_argument("--output-root", required=True, help="parent dir for each run's scoring output")
  return p.parse_args()


def rank_raters(prescoring_path, scorer_name):
  df = pd.read_csv(prescoring_path, sep="\t")
  df = df[df["scorerName"] == scorer_name].copy()
  df = df.dropna(subset=["internalRaterFactor1"])
  df["polarization"] = df["internalRaterFactor1"].abs()
  # Stable ordering: secondary key on raterParticipantId resolves |factor| ties.
  df = df.sort_values(["polarization", "raterParticipantId"], ascending=[False, True]).reset_index(drop=True)
  return df["raterParticipantId"].astype(str).tolist()


def build_grid(strategies, percents, reps, base_seed):
  for strategy in strategies:
    for pct in percents:
      if strategy == "random":
        for rep in range(reps):
          yield strategy, pct, rep, base_seed + rep
      else:
        yield strategy, pct, 0, -1


def select_ids(strategy, pct, seed, ranked_ids):
  n = len(ranked_ids)
  k = max(1, math.ceil(pct / 100.0 * n))
  if strategy == "extreme":
    return ranked_ids[:k]
  if strategy == "central":
    return ranked_ids[-k:]
  if strategy == "random":
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=k, replace=False)
    return [ranked_ids[i] for i in sorted(idx.tolist())]
  raise ValueError(f"unknown strategy {strategy!r}")


def main():
  args = parse_args()
  strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
  for s in strategies:
    if s not in STRATEGIES:
      raise SystemExit(f"unknown strategy {s!r}; expected subset of {STRATEGIES}")
  percents = [float(x) for x in args.percents.split(",")]

  ranked = rank_raters(args.prescoring_rater_output, args.scorer_name)
  print(f"ranked {len(ranked)} raters from {args.prescoring_rater_output} (scorer={args.scorer_name})")

  ids_dir = os.path.join(args.out_dir, "ids")
  os.makedirs(ids_dir, exist_ok=True)
  manifest_path = os.path.join(args.out_dir, "manifest.tsv")

  rows = []
  for strategy, pct, rep, seed in build_grid(strategies, percents, args.reps, args.base_seed):
    pct_str = f"{pct:g}"
    ids = select_ids(strategy, pct, seed, ranked)
    fname = f"{strategy}_{pct_str}pct_seed{seed}.txt"
    ids_path = os.path.join(ids_dir, fname)
    with open(ids_path, "w") as f:
      f.write("\n".join(ids) + "\n")
    output_dir = os.path.join(args.output_root, f"{strategy}_{pct_str}pct_seed{seed}")
    rows.append({
      "array_idx": len(rows),
      "strategy": strategy,
      "pct": pct_str,
      "rep": rep,
      "seed": seed,
      "num_kept": len(ids),
      "ids_path": os.path.abspath(ids_path),
      "output_dir": os.path.abspath(output_dir),
    })

  pd.DataFrame(rows).to_csv(manifest_path, sep="\t", index=False)
  print(f"wrote {len(rows)} rows to {manifest_path}")


if __name__ == "__main__":
  main()
