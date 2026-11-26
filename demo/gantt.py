"""
Desenha o diagrama de Gantt do trace gerado pelo nó polling_demo
(equivalente à Fig. 3 do artigo).

Uso:
    python gantt.py trace_single.csv            # gera trace_single.png
    python gantt.py trace_single.csv --show     # abre a janela

Leitura do gráfico:
  ▼ = instante em que a mensagem/request/timer chegou
  barra = execução da callback (500 ms cada)
Procure: (1) só UMA instância de cada callback por janela de processamento,
mesmo com duas mensagens na fila; (2) SM chegando durante uma janela e só
executando depois do próximo polling point; (3) se os timers furam ou não
os polling points (no Crystal, furavam).
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ORDER = ["t0", "t1", "t2", "t3", "H", "M", "L", "SH", "SM", "SL"]
COLORS = {"t": "#d1495b", "S": "#00798c", "_": "#edae49"}


def color(name):
    if name.startswith("t"):
        return COLORS["t"]
    if name.startswith("S"):
        return COLORS["S"]
    return COLORS["_"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = Path(sys.argv[1])
    runs, arrivals = defaultdict(list), defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a, b = float(row["inicio_ms"]), float(row["fim_ms"])
            if row["evento"] == "run":
                runs[row["nome"]].append((a, b))
            elif row["evento"] == "arrive":
                arrivals[row["nome"]].append((a, b))

    names = [n for n in ORDER if n in runs or n in arrivals]
    y = {n: i for i, n in enumerate(reversed(names))}

    fig, ax = plt.subplots(figsize=(11, 0.45 * len(names) + 1.5))
    for n in names:
        for a, b in runs[n]:
            ax.broken_barh([(a, b - a)], (y[n] - 0.35, 0.7), color=color(n), edgecolor="black", lw=.5)
        for a, _ in arrivals[n]:
            ax.plot(a, y[n] + 0.45, marker="v", color="black", ms=6)

    ax.set_yticks(list(y.values()))
    ax.set_yticklabels(list(y.keys()))
    ax.set_xlabel("tempo desde T0 (ms)")
    ax.set_title(f"Execução das callbacks — {path.stem}")
    ax.grid(axis="x", alpha=.3)
    fig.tight_layout()
    out = path.with_suffix(".png")
    fig.savefig(out, dpi=150)
    print(f"Gráfico salvo em {out}")

    # ordem de execução em texto, útil para os slides
    seq = sorted((a, n) for n, lst in runs.items() for a, _ in lst)
    print("Ordem de execução:", " ".join(n for _, n in seq))

    if "--show" in sys.argv:
        plt.show()


if __name__ == "__main__":
    main()
