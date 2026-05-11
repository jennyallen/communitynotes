#!/bin/bash
# Run the full helpfulness pipeline (prescoring + final scoring) 10 times against
# data_pre_june30/ with seeds 0-9. Each iteration writes to
# sourcecode/full_pipeline_runs/seed<N>/ with prescoring artifacts in a
# prescoring/ subdir.
# Run from the cluster: bash ablation/run_full_pipeline.sh
set -euo pipefail

cd /orcd/home/002/jnallen/communitynotes
source scoring/communitynotes_env/bin/activate

DATA_DIR=data_pre_june30
POOL=/home/jnallen/orcd/pool/communitynotes_data
OUT="$POOL/full_pipeline_runs"

mkdir -p "$POOL/logs" "$OUT"
echo "Submitting 10 full-pipeline tasks against $DATA_DIR..."
sbatch \
  --export=ALL,DATA_DIR="$DATA_DIR",OUTPUT_ROOT="$OUT" \
  ablation/run_full_pipeline.sbatch
