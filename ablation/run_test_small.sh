#!/bin/bash
# Small-data ablation test: 10% × 1 rep × 3 strategies = 3 SLURM array tasks
# against data_small/. Output goes to sourcecode/ablation_runs_small/.
# Run from the cluster: bash ablation/run_test_small.sh
set -euo pipefail

cd /orcd/home/002/jnallen/communitynotes
source scoring/communitynotes_env/bin/activate

DATA_DIR=data_small
POOL=/home/jnallen/orcd/pool/communitynotes_data
OUT="$POOL/ablation_runs_small"
IDS_DIR="$OUT/ids"
OUTPUT_ROOT="$OUT/runs"

mkdir -p "$POOL/logs" "$IDS_DIR" "$OUTPUT_ROOT"

python ablation/generate_samples.py \
  --prescoring-rater-output "sourcecode/$DATA_DIR/prescoring/prescoring_rater_model_output.tsv" \
  --strategies extreme,central,random \
  --percents 10 \
  --reps 1 \
  --out-dir "$OUT" \
  --output-root "$OUTPUT_ROOT"

N=$(ls "$IDS_DIR"/*.txt | wc -l)
echo "Submitting $N tasks against $DATA_DIR..."
sbatch --array=0-$((N-1)) \
  --export=ALL,IDS_DIR="$IDS_DIR",OUTPUT_ROOT="$OUTPUT_ROOT",DATA_DIR="$DATA_DIR" \
  ablation/run_ablation.sbatch
