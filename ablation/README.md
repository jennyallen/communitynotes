# Rater/Writer Ablation

Run final-scoring many times against a single shared prescoring run, each time keeping a different subset of raters/writers, to measure how the kept set affects which notes get surfaced.

## Pieces

- `generate_samples.py` — ranks raters by `|internalRaterFactor1|` from `prescoring_rater_model_output.tsv` and writes one ID file per `(strategy, pct, rep)` plus a manifest TSV.
- `run_ablation.sbatch` — SLURM array. Each task picks one ID file (sorted alphabetically, indexed by `$SLURM_ARRAY_TASK_ID`), parses the seed out of the filename, and runs `python main.py` with `--keep-participant-ids` and `--seed`.
- The runner-side filter (`--keep-participant-ids`) lives in [sourcecode/scoring/runner.py](../sourcecode/scoring/runner.py) and applies to both `notes` (by `noteAuthorParticipantId`) and `ratings` (by `raterParticipantId`).

## Strategies

| Strategy | Definition |
|---|---|
| `extreme` | top X% by `|internalRaterFactor1|` (deterministic; identical IDs across reps) |
| `central` | bottom X% (closest to factor 0; deterministic) |
| `random` | random X% sampled with `np.random.default_rng(base_seed + rep)` |

For all strategies, `--seed` is passed to MF, so even deterministic-rater-set strategies vary in MF init across reps.

## Test run (3 jobs: 10% × 1 rep × 3 strategies)

1. **Push your changes.** Locally, on `jennyedit`:
   ```bash
   git push origin jennyedit
   ```

2. **On the cluster, pull and run the wrapper:**
   ```bash
   cd /orcd/home/002/jnallen/communitynotes
   git pull
   bash ablation/run_test.sh
   ```
   The wrapper activates the venv, runs `generate_samples.py` to write 3 ID files into
   `sourcecode/ablation_runs/ids/`, then submits the sbatch with `--array=0-2`
   and the right `IDS_DIR`/`OUTPUT_ROOT` exported.

3. **Watch progress:**
   ```bash
   squeue -u $USER
   tail -f log_ablation_<jobid>_0.out       # alphabetically first task = central_10pct
   ```

   Each run writes its outputs (`scored_notes.tsv`, `helpfulness_scores.tsv`, etc.) under
   `sourcecode/ablation_runs/runs/<strategy>_10pct_seed0/`.

## Full grid

For a real run, scale up `--percents` and `--reps`:
```bash
python ablation/generate_samples.py \
  --prescoring-rater-output sourcecode/data_pre_june30/prescoring/prescoring_rater_model_output.tsv \
  --strategies extreme,central,random \
  --percents 10,25,50 \
  --reps 5 \
  --base-seed 0 \
  --out-dir sourcecode/ablation_runs \
  --output-root sourcecode/ablation_runs/runs
```
With `--strategies extreme,central,random --percents 10,25,50 --reps 5` you get
3 × 3 × 5 = **45 jobs**. Set `#SBATCH --array=0-44%10` to cap concurrency at 10.

The kept rater set for `extreme` and `central` is identical across the 5 reps (rank is deterministic); only the MF seed varies. If that's not useful, drop `--reps` to 1 for those strategies and run `random` separately at higher reps.
