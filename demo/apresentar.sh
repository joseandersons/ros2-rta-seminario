#!/usr/bin/env bash
# Roda o experimento ao vivo e mostra as callbacks sendo executadas numa janela.
# Uso (no Ubuntu/WSL):  bash ~/ros2-rta-seminario/demo/apresentar.sh [single]
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
rm -f "trace_$EX.csv"
echo "Executor: $EX   (o experimento dura ~10 s)"
echo

LIVE=""
if [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
  # janela ao vivo: abre antes e vai desenhando enquanto o experimento roda
  python3 "$DEMO/live.py" "trace_$EX.csv" &
  LIVE=$!
  sleep 2
fi

ros2 run polling_demo polling_demo "$EX"
echo
python3 "$DEMO/gantt.py" "trace_$EX.csv"

if [ -n "$LIVE" ]; then
  echo "Feche a janela do gráfico para terminar."
  wait "$LIVE" || true
elif command -v explorer.exe >/dev/null 2>&1; then
  # sem janela gráfica: abre a imagem no visualizador do Windows
  explorer.exe "$(wslpath -w "$OUT/trace_$EX.png")" || true
fi
