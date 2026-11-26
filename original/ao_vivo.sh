#!/usr/bin/env bash
# Roda o código ORIGINAL dos autores no ROS 2 Jazzy e mostra as callbacks ao vivo.
# O código deles não muda: o coletor.py só lê os logs que ele já imprime.
# Uso (no Ubuntu/WSL):  bash ~/ros2-rta-seminario/original/ao_vivo.sh
set -eo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
LIVE_PY="$AQUI/live.py"
WS="$HOME/orig_ws"
OUT="$AQUI/ao_vivo"
mkdir -p "$OUT" "$WS/src"

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
rm -rf "$WS/src/model_validation"
cp -r "$AQUI/model_validation" "$WS/src/"
chmod +x "$WS/src/model_validation/bin/send_cb_sequence"
echo "Compilando o código dos autores..."
(cd "$WS" && colcon build --packages-select model_validation >/dev/null 2>&1)
# shellcheck disable=SC1091
source "$WS/install/setup.bash"

cd "$OUT"
rm -f no.log script.log trace_autores.csv
export RCUTILS_LOGGING_BUFFERED_STREAM=0   # log do ROS sai na hora

# 1) nó dos autores (as callbacks)
arbitrary_cb_time > no.log 2>&1 &
NO=$!
trap 'kill "$NO" 2>/dev/null || true' EXIT

# 2) coletor: transforma os logs em trace, e a janela ao vivo desenha
python3 "$AQUI/coletor.py" no.log script.log trace_autores.csv &
COLETOR=$!
if [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
  python3 "$LIVE_PY" trace_autores.csv 9500 &
  LIVE=$!
fi
sleep 2

# 3) script dos autores (manda a sequência da Fig. 3), com o logging do Python
#    ligado só para sabermos quando ele envia cada lote
echo "Rodando o experimento dos autores (~9 s)..."
python3 -u -c "
import logging, runpy, sys
logging.basicConfig(level=logging.INFO, format='%(created).3f %(message)s')
sys.argv = ['send_cb_sequence']
runpy.run_path('$(command -v send_cb_sequence)', run_name='__main__')
" > script.log 2>&1
grep "execution order" script.log
wait "$COLETOR" || true

if [ -n "${LIVE:-}" ]; then
  echo "Feche a janela do gráfico para terminar."
  wait "$LIVE" || true
fi
