#!/usr/bin/env bash
# Compila e roda o código ORIGINAL dos autores (model_validation) no ROS 2 Jazzy.
# Uso (no Ubuntu/WSL):  bash rodar.sh [vezes]
set -eo pipefail

VEZES="${1:-1}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
WS="$HOME/orig_ws"

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
mkdir -p "$WS/src"
rm -rf "$WS/src/model_validation"
cp -r "$AQUI/model_validation" "$WS/src/"
chmod +x "$WS/src/model_validation/bin/send_cb_sequence"
(cd "$WS" && colcon build --packages-select model_validation >/dev/null)
# shellcheck disable=SC1091
source "$WS/install/setup.bash"

for i in $(seq "$VEZES"); do
  arbitrary_cb_time >/dev/null 2>&1 &
  NODE=$!
  sleep 2
  send_cb_sequence 2>&1 | grep "execution order"
  kill "$NODE" 2>/dev/null || true
  wait "$NODE" 2>/dev/null || true
done
