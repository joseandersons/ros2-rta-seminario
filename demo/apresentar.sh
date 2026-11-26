#!/usr/bin/env bash
# Roda o experimento ao vivo e abre o Gantt no Windows.
# Uso (no Ubuntu/WSL):  bash ~/ros2-rta-seminario/demo/apresentar.sh [single|events|multi]
set -eo pipefail

EX="${1:-single}"
DEMO="$(cd "$(dirname "$0")" && pwd)"
OUT="$DEMO/ao_vivo"
mkdir -p "$OUT"

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1091
source "$DEMO/ros2_ws/install/setup.bash"

cd "$OUT"
echo "Executor: $EX   (o experimento dura ~10 s)"
echo
ros2 run polling_demo polling_demo "$EX"
echo
python3 "$DEMO/gantt.py" "trace_$EX.csv"

# abre a imagem no visualizador do Windows (WSL)
if command -v explorer.exe >/dev/null 2>&1; then
  explorer.exe "$(wslpath -w "$OUT/trace_$EX.png")" || true
fi
