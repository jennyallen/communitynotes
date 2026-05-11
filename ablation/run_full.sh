#!/bin/bash
# Full ablation grid: 10/20/30% × 10 reps × 3 strategies = 90 SLURM array tasks
# against data_pre_june30/. Writes to sourcecode/ablation_runs/.
# Overwrites prior IDs/manifest in that dir.
# Run from the cluster: bash ablation/run_full.sh
set -euo pipefail

cd /orcd/home/002/jnallen/communitynotes
source scoring/communitynotes_env/bin/activate

DATA_DIR=data_pre_june30
POOL=/home/jnallen/orcd/pool/communitynotes_data
OUT="$POOL/ablation_runs"
IDS_DIR="$OUT/ids"
OUTPUT_ROOT="$OUT/runs"

# Clear stale IDs from previous (smaller) grids so SLURM array indexing matches
# the new manifest.
mkdir -p "$POOL/logs" "$IDS_DIR" "$OUTPUT_ROOT"
rm -f "$IDS_DIR"/*.txt

python ablation/generate_samples.py \
  --prescoring-rater-output "sourcecode/$DATA_DIR/prescoring/prescoring_rater_model_output.tsv" \
  --strategies extreme,central,random \
  --percents 10,20,30 \
  --reps 10 \
  --base-seed 0 \
  --out-dir "$OUT" \
  --output-root "$OUTPUT_ROOT"

N=$(ls "$IDS_DIR"/*.txt | wc -l)
echo "Submitting $N tasks against $DATA_DIR (concurrency cap 10)..."
sbatch --array=0-$((N-1))%10 \
  --export=ALL,IDS_DIR="$IDS_DIR",OUTPUT_ROOT="$OUTPUT_ROOT",DATA_DIR="$DATA_DIR" \
  ablation/run_ablation.sbatch
