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

# conda-forge has prebuilt R packages including the heavyweight arrow; avoid CRAN compile.
conda create -n "$ENV_NAME" -c conda-forge -y \
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
  jupyterlab

# Register the R kernel for Jupyter (writes to ~/.local/share/jupyter/kernels/).
conda run -n "$ENV_NAME" Rscript -e \
  'IRkernel::installspec(name = "ir-cn", displayname = "R (cn_r_analysis)", user = TRUE)'

echo ""
echo "Done. Activate with:   conda activate $ENV_NAME"
echo "Launch jupyter with:   jupyter lab --no-browser --port=8889 --ip=0.0.0.0"
echo "Then in the notebook, pick the kernel 'R (cn_r_analysis)'."
