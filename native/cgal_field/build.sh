#!/usr/bin/env bash
# Builds cgal_field - CGAL's mesher on a distance field or a closed surface, compiled - into the WSL
# micromamba environment `fieldmesh`, made once with:
#   micromamba create -n fieldmesh -c conda-forge python=3.12 numpy scipy cgal-cpp tbb-devel pybind11 cxx-compiler
# then, from WSL:  bash native/cgal_field/build.sh
# fastcae calls it through src/fastcae/simulate/wsl_mesher.py.
set -euo pipefail
PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.local/share/mamba}/envs/fieldmesh"
PY="$PREFIX/bin/python"
SITE=$("$PY" -c "import sysconfig; print(sysconfig.get_paths()['platlib'])")
SUFFIX=$("$PY" -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
"$PREFIX/bin/x86_64-conda-linux-gnu-c++" -O3 -DNDEBUG -std=c++17 -shared -fPIC \
  $("$PY" -m pybind11 --includes) -isystem "$PREFIX/include" -DCGAL_LINKED_WITH_TBB \
  "$(dirname "$0")/cgal_field.cpp" -o "$SITE/cgal_field$SUFFIX" \
  -L"$PREFIX/lib" -Wl,-rpath,"$PREFIX/lib" -ltbb -ltbbmalloc -lgmp -lmpfr
echo "built $SITE/cgal_field$SUFFIX"
