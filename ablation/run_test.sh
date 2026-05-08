#!/bin/bash
# Small ablation test: 10% × 1 rep × 3 strategies = 3 SLURM array tasks.
# Activates the venv, generates IDs, submits the sbatch with the right --array.
# Run from the cluster: bash ablation/run_test.sh
set -euo pipefail

cd /orcd/home/002/jnallen/communitynotes
source scoring/communitynotes_env/bin/activate

OUT=sourcecode/ablation_runs_small
IDS_DIR="$(pwd)/$OUT/ids"
OUTPUT_ROOT="$(pwd)/$OUT/runs"

python ablation/generate_samples.py \
  --prescoring-rater-output sourcecode/data_small/prescoring/prescoring_rater_model_output.tsv \
  --strategies extreme,central,random \
  --percents 10 \
  --reps 1 \
  --out-dir "$OUT" \
  --output-root "$OUT/runs"

N=$(ls "$IDS_DIR"/*.txt | wc -l)
echo "Submitting $N tasks..."
sbatch --array=0-$((N-1)) \
  --export=ALL,IDS_DIR="$IDS_DIR",OUTPUT_ROOT="$OUTPUT_ROOT" \
  ablation/run_ablation.sbatch
