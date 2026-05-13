#!/bin/bash
# Set up a conda env with R + the packages ablation_analysis.ipynb needs,
# and register it as a Jupyter kernel. Run once on the MIT Engaging cluster.
#
#   bash ablation/setup_r_env.sh
#
# Then to run the notebook:
#   conda activate cn_r_analysis
#   jupyter lab --no-browser --port=8889 --ip=0.0.0.0
# and on your laptop:
#   ssh -L 8889:<compute_node>:8889 jnallen@orcd.mit.edu
# then open http://localhost:8889 in a browser and pick the
# "R (cn_r_analysis)" kernel.
set -euo pipefail

ENV_NAME="${ENV_NAME:-cn_r_analysis}"

# Engaging usually exposes conda via a module. If `conda` isn't already on
# PATH, try loading miniforge / miniconda. Adjust to whatever `module avail
# conda` shows on your node.
if ! command -v conda >/dev/null 2>&1; then
  module load miniforge/24.3.0-0 2>/dev/null \
    || module load miniconda3 2>/dev/null \
    || { echo "conda not found and 'module load' couldn't supply it. Install miniforge or load the right module first." >&2; exit 1; }
fi

# Idempotent: blow away any prior (possibly partial) env with the same name.
conda env remove -n "$ENV_NAME" -y 2>/dev/null || true

# Use the libmamba solver — conda's classic solver hangs for many minutes on
# the R-package dependency graph. libmamba ships with conda >=23.x and is the
# default in newer versions. If it's not available on your conda, drop the flag.
#
# conda-forge has prebuilt R packages including the heavyweight arrow; avoid CRAN compile.
# Pin python=3.12 — JupyterLab + Engaging OOD's proxy choked on python 3.14.
# notebook is needed because OOD's Jupyter loads the notebook-server extension.
conda create -n "$ENV_NAME" --solver=libmamba -c conda-forge -y \
  'python=3.12' \
  r-base \
  r-irkernel \
  r-arrow \
  r-data.table \
  r-dplyr \
  r-tibble \
  r-tidyr \
  r-ggplot2 \
  r-patchwork \
  r-stringr \
  r-purrr \
  r-scales \
  jupyterlab \
  notebook

# Register the R kernel for Jupyter. R_LIBS_USER="" for THIS call only — your
# ~/.Renviron and personal lib (e.g. /home/jnallen/R/libs) are untouched.
# Without it, a stale pre-R-4.0 'uuid' there can break IRkernel::installspec.
R_LIBS_USER="" conda run -n "$ENV_NAME" Rscript -e \
  'IRkernel::installspec(user = TRUE)'

# Patch the kernel.json so OOD launches the kernel with the conda env's R by
# absolute path (instead of relying on PATH, which OOD doesn't always activate)
# and with R_LIBS_USER cleared (so the running kernel doesn't pick up the same
# stale personal library and crash mid-notebook).
KERNEL_JSON="$HOME/.local/share/jupyter/kernels/ir/kernel.json"
if [ ! -f "$KERNEL_JSON" ]; then
  KERNEL_JSON="$HOME/.conda/envs/$ENV_NAME/share/jupyter/kernels/ir/kernel.json"
fi
python3 - "$KERNEL_JSON" "$HOME/.conda/envs/$ENV_NAME/bin/R" <<'PY'
import json, sys
path, r_bin = sys.argv[1], sys.argv[2]
with open(path) as f:
    spec = json.load(f)
spec["argv"][0] = r_bin
spec.setdefault("env", {})["R_LIBS_USER"] = ""
with open(path, "w") as f:
    json.dump(spec, f, indent=2)
print("patched", path)
PY

echo ""
echo "Done. Activate with:   conda activate $ENV_NAME"
echo "Launch jupyter with:   jupyter lab --no-browser --port=8889 --ip=0.0.0.0"
echo "Then in the notebook, pick the kernel 'R (cn_r_analysis)'."
