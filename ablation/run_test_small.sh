#!/bin/bash
# Small-data ablation test: 10% × 1 rep × 3 strategies = 3 SLURM array tasks
# against data_small/. Output goes to sourcecode/ablation_runs_small/.
# Run from the cluster: bash ablation/run_test_small.sh
set -euo pipefail

cd /orcd/home/002/jnallen/communitynotes
source scoring/communitynotes_env/bin/activate

DATA_DIR=data_small
OUT=sourcecode/ablation_runs_small
IDS_DIR="$(pwd)/$OUT/ids"
OUTPUT_ROOT="$(pwd)/$OUT/runs"

python ablation/generate_samples.py \
  --prescoring-rater-output "sourcecode/$DATA_DIR/prescoring/prescoring_rater_model_output.tsv" \
  --strategies extreme,central,random \
  --percents 10 \
  --reps 1 \
  --out-dir "$OUT" \
  --output-root "$OUT/runs"

mkdir -p sourcecode/logs
N=$(ls "$IDS_DIR"/*.txt | wc -l)
echo "Submitting $N tasks against $DATA_DIR..."
sbatch --array=0-$((N-1)) \
  --export=ALL,IDS_DIR="$IDS_DIR",OUTPUT_ROOT="$OUTPUT_ROOT",DATA_DIR="$DATA_DIR" \
  ablation/run_ablation.sbatch
