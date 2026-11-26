"""
Visualização ao vivo do experimento (Fig. 3 do artigo).

Abre uma janela e desenha as callbacks enquanto o experimento roda:
as barras crescem enquanto a callback executa, os ▼ aparecem quando a
mensagem/timer chega e a linha tracejada cinza mostra quanto tempo cada
uma ficou esperando o executor.

Uso (o ao_vivo.sh já faz isso):
    python3 live.py trace_single.csv [duração_ms]

Funciona com o trace da nossa reprodução (H, M, L, SH...) e com o trace do
código original dos autores (high, medium, low, srv_high..., timer0...).
"""
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

ORDER_NOSSO = ["t0", "t1", "t2", "t3", "H", "M", "L", "SH", "SM", "SL"]
ORDER_AUTORES = ["timer0", "timer1", "timer2", "timer3", "high", "medium", "low",
                 "srv_high", "srv_medium", "srv_low"]
COLORS = {"t": "#d1495b", "S": "#00798c", "_": "#edae49"}
XMAX = 9000  # ms; o experimento termina por volta de 8500 ms


def color(name):
    if name.startswith("t"):
        return COLORS["t"]
    if name.startswith("S") or name.startswith("srv_"):
        return COLORS["S"]
    return COLORS["_"]


class Trace:
    """Lê o CSV aos poucos, enquanto o experimento escreve nele."""

    def __init__(self, path):
        self.path = path
        self.pos = 0
        self.epoch = None
        self.arrive = defaultdict(list)
        self.start = defaultdict(list)
        self.end = defaultdict(list)

    def poll(self):
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            f.seek(self.pos)
            while True:
                line = f.readline()
                if not line.endswith("\n"):
                    break  # linha ainda sendo escrita
                self.pos = f.tell()
                parts = line.strip().split(",")
                if len(parts) != 4 or parts[0] == "evento":
                    continue
                ev, name, a, b = parts[0], parts[1], float(parts[2]), float(parts[3])
                if ev == "epoch":
                    self.epoch = a
                elif ev == "arrive":
                    self.arrive[name].append(a)
                elif ev == "start":
                    self.start[name].append(a)
                elif ev == "run":
                    self.end[name].append(b)


def tipo(n):
    """Ordem do executor entre tipos: timers, subscribers, services."""
    if n.startswith("t"):
        return 0
    if n.startswith("S") or n.startswith("srv_"):
        return 2
    return 1


def comandas(tr, nomes):
    """Deduz as comandas (readySet) pelo modelo do artigo.

    O ROS 2 não registra os polling points, então eles são reconstruídos:
    cada comanda começa quando a primeira callback dela começa e contém,
    uma vez cada, todas as callbacks que já estavam prontas naquele instante.
    Ela termina quando essas callbacks rodaram; aí vem a próxima.
    Devolve [(início_ms, [nomes na ordem em que rodaram/vão rodar]), ...].
    """
    seq = sorted((s, n) for n in nomes for s in tr.start[n])
    res, i = [], 0
    while i < len(seq):
        pp = seq[i][0]
        feitos = defaultdict(int)
        for _, m in seq[:i]:
            feitos[m] += 1
        prontos = [n for n in nomes
                   if sum(1 for a in tr.arrive[n] if a <= pp + 1) > feitos[n]]
        k = max(1, len(prontos))
        membros = [m for _, m in seq[i:i + k]]
        membros += [n for n in sorted(prontos, key=tipo) if n not in membros]
        res.append((pp, membros))
        i += k
    return res


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    global XMAX
    tr = Trace(Path(sys.argv[1]))
    if len(sys.argv) > 2:
        XMAX = float(sys.argv[2])
    ORDER = ORDER_AUTORES if "autores" in sys.argv[1] else ORDER_NOSSO
    y = {n: i for i, n in enumerate(reversed(ORDER))}

    plt.rcParams.update({"font.size": 14})
    fig, ax = plt.subplots(figsize=(14, 7.5))
    fig.canvas.manager.set_window_title("Executor do ROS 2 ao vivo")
    salvo = []

    def draw(_):
        tr.poll()
        ax.clear()
        if tr.epoch is None:
            now = 0.0
            status = "aguardando o experimento começar..."
        else:
            now = min(time.time() * 1000 - tr.epoch, XMAX)
            running = [n for n in ORDER if len(tr.start[n]) > len(tr.end[n])]
            status = f"rodando: {running[0]}" if running else "executor olhando a fila"
            if now >= XMAX:
                status = "fim"

        for n in ORDER:
            yy = y[n]
            arrivals = sorted(a for a in tr.arrive[n] if a <= now)
            starts = tr.start[n]
            # espera: da chegada até começar a rodar (ou até agora)
            for k, a in enumerate(arrivals):
                fim = starts[k] if k < len(starts) else now
                if fim > a:
                    ax.plot([a, fim], [yy, yy], color="#8a8a8a", ls=(0, (4, 3)), lw=2, zorder=1)
            # execução: barra que cresce enquanto a callback roda
            for k, s in enumerate(starts):
                e = tr.end[n][k] if k < len(tr.end[n]) else now
                rodando = k >= len(tr.end[n])
                ax.broken_barh([(s, max(e - s, 1))], (yy - 0.35, 0.7), color=color(n),
                               edgecolor="black", lw=2.5 if rodando else 0.6, zorder=2)
            for a in arrivals:
                ax.plot(a, yy + 0.5, marker="v", color="black", ms=9, zorder=3)

        # comandas: faixas alternadas, linha no polling point e o número
        cmds = comandas(tr, ORDER) if tr.epoch is not None else []
        topo = len(ORDER) + 0.15
        for i, (pp, membros) in enumerate(cmds):
            fim = cmds[i + 1][0] if i + 1 < len(cmds) else now
            if i % 2 == 0:
                ax.axvspan(pp, fim, color="#E9EEF1", zorder=0)
            ax.axvline(pp, color="#4A5866", lw=1.2, alpha=0.8, zorder=1)
            rotulo = f"comanda {i + 1}" if fim - pp > 900 else f"{i + 1}"
            ax.text(pp + 40, topo, rotulo, fontsize=13, color="#14202B",
                    va="center", ha="left", fontweight="bold")
        if cmds and status != "fim":
            status += f"\ncomanda {len(cmds)}: " + ", ".join(cmds[-1][1])

        ax.axvline(now, color="#14202B", lw=1.5, alpha=0.6)
        ax.set_xlim(-100, XMAX)
        ax.set_ylim(-0.7, len(ORDER) + 0.5)
        ax.set_yticks(list(y.values()))
        ax.set_yticklabels(list(y.keys()))
        ax.set_xlabel("tempo desde o início (ms)")
        ax.set_title(f"{now / 1000:4.1f} s   ·   {status}", loc="left")
        ax.grid(axis="x", alpha=0.3)
        ax.legend(handles=[
            Patch(color=COLORS["t"], label="timers"),
            Patch(color=COLORS["_"], label="subscribers"),
            Patch(color=COLORS["S"], label="services"),
            Line2D([], [], marker="v", color="black", ls="", ms=9, label="chegada"),
            Line2D([], [], color="#8a8a8a", ls=(0, (4, 3)), lw=2, label="esperando"),
        ], loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=5, frameon=False)
        fig.tight_layout()
        # no fim, salva o quadro final como imagem (ao lado do CSV)
        if status == "fim" and not salvo:
            fig.savefig(tr.path.with_suffix(".png"), dpi=150)
            salvo.append(True)

    anim = FuncAnimation(fig, draw, interval=50, cache_frame_data=False)  # noqa: F841
    plt.show()


if __name__ == "__main__":
    main()
