"""
Calculadora da análise de tempo de resposta (RTA) de
Casini et al., "Response-Time Analysis of ROS 2 Processing Chains under
Reservation-Based Scheduling", ECRTS 2019.

Implementa, para UMA reserva (um executor single-threaded):
  - sbf(Δ) do modelo de recurso periódico (Q, P)        -> Seção 2.2
  - Lema 3  : timers (prioridade fixa não preemptiva)    -> Eq. (3)
  - Eq. (6) : callbacks baseadas em polling point (subs) -> Lemas 4 e 5
  - Lema 6  : duração do busy period (limita a busca em A)
  - Lema 7  : só testar os A onde rbf_i muda
  - Seção 5.1: propagação de jitter (CPA) para obter a latência da cadeia
  - Lema 8  : análise holística da subcadeia (paga a rajada uma vez só)

Também calcula, para comparação, o que se obteria SE o executor respeitasse
as prioridades (todas as callbacks analisadas como timers, i.e., prioridade
fixa não preemptiva clássica, igual à RTA vista em aula com bloqueio).

Tempo discreto, unidade = 1 ms. Uso:
    python rta_ros2.py            # exemplo + varredura do orçamento
    python rta_ros2.py --plot     # idem, salvando um gráfico (matplotlib)
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


@dataclass
class Callback:
    name: str
    kind: str            # "timer" ou "sub"
    e: int               # WCET (ms)
    period: int | None = None   # só para fontes (timers): período de ativação
    pred: str | None = None     # callback que publica no tópico desta (subs)
    # preenchidos pela análise:
    jitter: int = 0
    R: int = 0

    def __post_init__(self):
        if self.kind not in ("timer", "sub"):
            raise ValueError(self.kind)


@dataclass
class System:
    Q: int                       # orçamento da reserva
    P: int                       # período da reserva
    callbacks: list[Callback]    # em ORDEM DE PRIORIDADE do executor
    by_name: dict = field(init=False)

    def __post_init__(self):
        self.by_name = {c.name: c for c in self.callbacks}

    # --- função de oferta (supply bound function) --------------------------
    def sbf(self, t: int) -> int:
        """Serviço mínimo garantido pela reserva (Q, P) em qualquer janela t.
        Modelo de recurso periódico (Shin & Lee): pior caso = 2(P-Q) sem CPU."""
        Q, P = self.Q, self.P
        if Q >= P:                       # núcleo dedicado (SCHED_FIFO): sbf = t
            return max(0, t)
        if t <= P - Q:
            return 0
        y = (t - (P - Q)) // P
        return y * Q + max(0, t - 2 * (P - Q) - y * P)

    # --- curvas de ativação -------------------------------------------------
    def source_period(self, c: Callback) -> int:
        while c.pred is not None:
            c = self.by_name[c.pred]
        return c.period

    def eta(self, c: Callback, delta: int) -> int:
        """Máximo de ativações de c em janela de tamanho delta.
        Fonte periódica: ceil(Δ/T). Sucessoras herdam o período da fonte e
        acumulam jitter = tempos de resposta dos predecessores (CPA)."""
        if delta <= 0:
            return 0
        T = self.source_period(c)
        return math.ceil((delta + c.jitter) / T)

    def rbf(self, c: Callback, delta: int) -> int:
        return self.eta(c, delta) * c.e

    def RBF(self, cs, delta: int) -> int:
        return sum(self.rbf(c, delta) for c in cs)

    # --- conjuntos ------------------------------------------------------------
    def hp(self, c):
        i = self.callbacks.index(c)
        return self.callbacks[:i]

    def lp(self, c):
        i = self.callbacks.index(c)
        return self.callbacks[i + 1:]


HORIZON = 100_000  # evita laço infinito se a reserva estiver sobrecarregada


def least_fixed_point(lhs, rhs, start: int) -> int | None:
    """Menor x >= start tal que lhs(x) >= rhs(x)."""
    x = start
    while x < HORIZON:
        if lhs(x) >= rhs(x):
            return x
        x += 1
    return None


# ---------------------------------------------------------------------------
# Análise de uma callback isolada (Seção 5.2)
# ---------------------------------------------------------------------------


def blocking(sys: System, c: Callback) -> int:
    """Lema 2: bloqueio não preemptivo = maior WCET de prioridade menor."""
    return max((x.e for x in sys.lp(c)), default=0)


def response_time(sys: System, c: Callback, mode: str) -> int | None:
    """mode = 'ros'   -> regras do artigo (timers: Lema 3; subs: Eq. 6)
       mode = 'ideal' -> como se o executor respeitasse prioridades
                          (todas analisadas pelo Lema 3)."""
    as_timer = c.kind == "timer" or mode == "ideal"
    others = [x for x in sys.callbacks if x is not c]
    B = blocking(sys, c) if as_timer else 0
    interferers = sys.hp(c) if as_timer else others

    # Lema 6: limite do busy period
    L = least_fixed_point(
        sys.sbf,
        lambda L: sys.RBF(interferers, L) + B + sys.rbf(c, L),
        start=1,
    )
    if L is None:
        return None

    # Lema 7: candidatos A = {0} ∪ {A | rbf_i(A+1) != rbf_i(A)}
    cands = [0] + [A for A in range(1, L + 1) if sys.rbf(c, A + 1) != sys.rbf(c, A)]

    worst = 0
    for A in cands:
        # Eq. (3) (timer) ou Eq. (6) (pp-based):
        #   sbf(A+R) >= rbf_i(A+1) + RBF(interf, A+R-e+1) + B
        R = least_fixed_point(
            lambda R: sys.sbf(A + R),
            lambda R: sys.rbf(c, A + 1) + sys.RBF(interferers, A + R - c.e + 1) + B,
            start=c.e,
        )
        if R is None:
            return None
        worst = max(worst, R)
    return worst


def analyze_all(sys: System, mode: str, max_iter: int = 50) -> bool:
    """Iteração CPA: jitter das sucessoras = soma dos R dos predecessores;
    repete até o ponto fixo (Seção 5.1). Retorna False se não convergir."""
    for c in sys.callbacks:
        c.jitter, c.R = 0, 0
    for _ in range(max_iter):
        changed = False
        for c in sys.callbacks:
            R = response_time(sys, c, mode)
            if R is None:
                return False
            if R != c.R:
                c.R, changed = R, True
        for c in sys.callbacks:
            j = 0
            p = c.pred
            while p is not None:
                j += sys.by_name[p].R
                p = sys.by_name[p].pred
            # jitter de ativação = atraso máximo até c ser ativada,
            # menos o melhor caso (aqui, conservadoramente, 0)
            if j != c.jitter:
                c.jitter, changed = j, True
        if not changed:
            return True
    return False


# ---------------------------------------------------------------------------
# Cadeias (Seções 5.1 e 5.4)
# ---------------------------------------------------------------------------


def chain_latency_sum(sys: System, chain: list[str]) -> int:
    """CPA básico: soma dos tempos de resposta individuais (δ = 0, mesma reserva)."""
    return sum(sys.by_name[n].R for n in chain)


def chain_latency_holistic(sys: System, chain: list[str]) -> int | None:
    """Lema 8: subcadeia inteira numa reserva.
       sbf(R) >= RBF(Γ_k, R - e_last + 1)
    onde Γ_k = a própria subcadeia (rbf = η_fonte * soma dos e) + cada
    callback fora da cadeia como uma subcadeia de 1 elemento."""
    members = [sys.by_name[n] for n in chain]
    src, last = members[0], members[-1]
    e_chain = sum(c.e for c in members)
    outsiders = [c for c in sys.callbacks if c.name not in chain]

    def demand(R):
        d = R - last.e + 1
        own = sys.eta(src, d) * e_chain
        return own + sys.RBF(outsiders, d)

    return least_fixed_point(sys.sbf, demand, start=e_chain)


# ---------------------------------------------------------------------------
# Exemplo
# ---------------------------------------------------------------------------


def example_system(Q: int = 6, P: int = 10) -> System:
    """Um executor com uma cadeia sensor -> filtro -> controle e carga extra.
    Ordem da lista = prioridade no executor ROS 2:
    timers primeiro, depois subscribers (na ordem de registro)."""
    return System(Q=Q, P=P, callbacks=[
        Callback("t_sensor",   "timer", e=5,  period=100),
        Callback("t_diag",     "timer", e=2,  period=50),
        Callback("t_log",      "timer", e=15, period=200),
        Callback("s_filtro",   "sub",   e=10, pred="t_sensor"),
        Callback("s_controle", "sub",   e=8,  pred="s_filtro"),
        Callback("s_diag",     "sub",   e=6,  pred="t_diag"),
    ])


CHAIN = ["t_sensor", "s_filtro", "s_controle"]


def report(Q: int, P: int) -> None:
    print(f"\n=== Reserva Q={Q} ms a cada P={P} ms  (banda {Q/P:.0%}) ===")
    util = sum(c.e / example_system().source_period(c) for c in example_system().callbacks)
    print(f"Utilização da carga: {util:.1%}")
    rows = {}
    for mode in ("ideal", "ros"):
        s = example_system(Q, P)
        ok = analyze_all(s, mode)
        rows[mode] = (s, ok)

    print(f"{'callback':<12}{'tipo':<7}{'e':>4}  {'R ideal (prio fixa NP)':>24}  {'R ROS 2 (artigo)':>18}")
    for c_i, c_r in zip(rows["ideal"][0].callbacks, rows["ros"][0].callbacks):
        ri = c_i.R if rows["ideal"][1] else "∞"
        rr = c_r.R if rows["ros"][1] else "∞"
        print(f"{c_r.name:<12}{c_r.kind:<7}{c_r.e:>4}  {ri:>24}  {rr:>18}")

    s, ok = rows["ros"]
    if ok:
        print(f"\nCadeia {' -> '.join(CHAIN)}:")
        print(f"  soma dos R individuais (CPA básico) : {chain_latency_sum(s, CHAIN)} ms")
        print(f"  análise holística (Lema 8)          : {chain_latency_holistic(s, CHAIN)} ms")
    else:
        print("\nReserva insuficiente: análise não converge (sobrecarga).")


def sweep(P: int = 10):
    out = []
    for Q in range(1, P + 1):
        s = example_system(Q, P)
        if not analyze_all(s, "ros"):
            out.append((Q, None, None))
            continue
        out.append((Q, chain_latency_sum(s, CHAIN), chain_latency_holistic(s, CHAIN)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true", help="salva sweep.png")
    args = ap.parse_args()

    report(6, 10)
    report(10, 10)   # núcleo dedicado (SCHED_FIFO), sbf(Δ) = Δ

    print("\n=== Varredura do orçamento (como a Fig. 8a do artigo) ===")
    print(f"{'Q/P':>6} {'soma R':>8} {'holística':>10}")
    data = sweep()
    for Q, a, b in data:
        print(f"{Q*10:>5}% {a if a is not None else '∞':>8} {b if b is not None else '∞':>10}")

    if args.plot:
        import matplotlib.pyplot as plt
        xs = [Q * 10 for Q, a, _ in data if a is not None]
        plt.plot(xs, [a for _, a, _ in data if a is not None], "o-", label="soma dos R (sem cadeia)")
        plt.plot(xs, [b for _, a, b in data if a is not None], "s-", label="holística (Lema 8)")
        plt.xlabel("Orçamento da reserva (% do núcleo)")
        plt.ylabel("Latência fim a fim da cadeia (ms)")
        plt.title("Cadeia sensor → filtro → controle")
        plt.grid(alpha=.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig("sweep.png", dpi=150)
        print("\nGráfico salvo em sweep.png")


if __name__ == "__main__":
    main()
