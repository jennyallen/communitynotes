#!/bin/bash

#SBATCH --job-name=notes_full_pipeline
#SBATCH --output=/home/jnallen/orcd/pool/communitynotes_data/logs/log_pipeline_%A_%a.out
#SBATCH --partition=sched_mit_sloan_interactive
#SBATCH --cpus-per-task=8
#SBATCH --mem=500G
#SBATCH --time=1-00:00:00
#SBATCH --array=0-9

# Defaults; override with --export=ALL,DATA_DIR=...,OUTPUT_ROOT=...
DATA_DIR="${DATA_DIR:-data_pre_june30}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/orcd/home/002/jnallen/communitynotes/sourcecode/full_pipeline_runs}"

source /orcd/home/002/jnallen/communitynotes/scoring/communitynotes_env/bin/activate
cd /orcd/home/002/jnallen/communitynotes/sourcecode

SEED=$SLURM_ARRAY_TASK_ID
OUTPUT_DIR="$OUTPUT_ROOT/seed$SEED"
PRESCORING_DIR="$OUTPUT_DIR/prescoring"
mkdir -p "$PRESCORING_DIR"

echo "[$(date)] seed=$SEED  out=$OUTPUT_DIR  data=$DATA_DIR"

python main.py \
    --enrollment "$DATA_DIR/userEnrollment-00000.tsv" \
    --notes "$DATA_DIR/notes-00000.tsv" \
    --ratings "$DATA_DIR/ratings" \
    --status "$DATA_DIR/noteStatusHistory-00000.tsv" \
    --outdir "$OUTPUT_DIR" \
    --prescoring-outdir "$PRESCORING_DIR" \
    --seed "$SEED" \
    --nocheck-flips \
    --nostrict-columns \
    --parallel
