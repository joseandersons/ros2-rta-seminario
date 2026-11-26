#!/usr/bin/env bash
# Instala o ROS 2 Jazzy, compila a demo e roda o experimento nos 3 executores.
# Uso (no Ubuntu 24.04 / WSL2):
#   bash setup_wsl.sh
# Pode ser rodado de novo: pula o que já estiver instalado.
set -eo pipefail

REPO_URL="https://github.com/joseandersons/ros2-rta-seminario.git"
REPO="${REPO:-$HOME/ros2-rta-seminario}"

step() { echo; echo "==== $* ===="; }

# ---------------------------------------------------------------- ROS 2 Jazzy
if [ ! -f /opt/ros/jazzy/setup.bash ]; then
  step "1/4 Instalando ROS 2 Jazzy (pede a senha do sudo; ~10-15 min)"
  sudo apt-get update
  sudo apt-get install -y software-properties-common curl git
  sudo add-apt-repository -y universe
  VER=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
        | grep -F '"tag_name"' | awk -F'"' '{print $4}')
  CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
  curl -fL -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${VER}/ros2-apt-source_${VER}.${CODENAME}_all.deb"
  sudo dpkg -i /tmp/ros2-apt-source.deb
  sudo apt-get update
  sudo apt-get install -y ros-jazzy-ros-base ros-dev-tools python3-matplotlib
else
  step "1/4 ROS 2 Jazzy já instalado"
  python3 -c "import matplotlib" 2>/dev/null || sudo apt-get install -y python3-matplotlib
fi

# ---------------------------------------------------------------- repositório
step "2/4 Repositório em $REPO"
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" pull --ff-only
else
  git clone "$REPO_URL" "$REPO"
fi

# ---------------------------------------------------------------- build
step "3/4 Compilando (colcon build)"
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
cd "$REPO/demo/ros2_ws"
colcon build
# shellcheck disable=SC1091
source install/setup.bash

# ---------------------------------------------------------------- experimento
step "4/4 Rodando o experimento (~10 s)"
OUT="$REPO/demo/results"
mkdir -p "$OUT"
cd "$OUT"
for ex in single; do
  echo; echo "--- executor: $ex ---"
  if ros2 run polling_demo polling_demo "$ex" > "log_$ex.txt" 2>&1; then
    python3 "$REPO/demo/gantt.py" "trace_$ex.csv" | tail -n 2
  else
    echo "falhou (veja $OUT/log_$ex.txt)"
  fi
done

step "Pronto"
echo "Resultados (CSV, PNG e logs) em: $OUT"
