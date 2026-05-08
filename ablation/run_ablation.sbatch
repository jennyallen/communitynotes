#!/bin/bash

#SBATCH --job-name=notes_ablation
#SBATCH --output=log_ablation_%A_%a.out
#SBATCH --partition=sched_mit_sloan_interactive
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=2:00:00
#SBATCH --array=0-0      # edit this to (count of *.txt in IDS_DIR) - 1, e.g. --array=0-44%10

# Defaults below; override at submit time, e.g.
#   sbatch --array=0-2 --export=ALL,IDS_DIR=/path/ids,OUTPUT_ROOT=/path/runs ablation/run_ablation.sbatch
IDS_DIR="${IDS_DIR:-/orcd/home/002/jnallen/communitynotes/sourcecode/ablation_runs/ids}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/orcd/home/002/jnallen/communitynotes/sourcecode/ablation_runs/runs}"

source /orcd/home/002/jnallen/communitynotes/scoring/communitynotes_env/bin/activate
cd /orcd/home/002/jnallen/communitynotes/sourcecode

# Pick this task's IDs file (sorted alphabetically).
shopt -s nullglob
IDS_FILES=( "$IDS_DIR"/*.txt )
IDS_FILE="${IDS_FILES[$SLURM_ARRAY_TASK_ID]}"
NAME=$(basename "$IDS_FILE" .txt)         # e.g. random_25pct_seed3
SEED="${NAME##*seed}"                      # tail after "seed", e.g. 3
OUTPUT_DIR="$OUTPUT_ROOT/$NAME"
mkdir -p "$OUTPUT_DIR"

echo "[$(date)] array=$SLURM_ARRAY_TASK_ID  ids=$IDS_FILE  seed=$SEED  out=$OUTPUT_DIR"

python main.py \
    --enrollment data_small/userEnrollment-00000.tsv \
    --notes data_small/notes-00000.tsv \
    --ratings data_small/ratings \
    --status data_small/noteStatusHistory-00000.tsv \
    --outdir "$OUTPUT_DIR" \
    --scorers MFCoreScorer \
    --prescoring-indir data_small/prescoring \
    --keep-participant-ids "$IDS_FILE" \
    --seed "$SEED" \
    --nocheck-flips \
    --nostrict-columns
