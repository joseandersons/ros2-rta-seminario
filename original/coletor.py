"""
Transforma os logs do código ORIGINAL dos autores num trace CSV, enquanto o
experimento roda, para a janela ao vivo (live.py) desenhar.

O código dos autores não é alterado: só lemos o que ele já imprime.
  - nó arbitrary_cb_time (log do ROS, com horário):
      "Setting up timer #i in X ms"   -> o timer i vence X ms depois
      "Received <tipo> on <nome> ..." -> a callback começou
      "Finished <tipo> on <nome>"     -> a callback terminou
  - script send_cb_sequence (rodado com o logging do Python ligado):
      "Callback sending order (...): ..." -> a sequência enviada
      "Sending callbacks"                 -> 1º lote enviado (vira o instante 0)
      "Processing sent callbacks"         -> 2º lote (depois dos 'delay') enviado

Uso: python3 coletor.py no.log script.log trace.csv
"""
import re
import sys
import time
from pathlib import Path

RE_ROS = re.compile(r"^\[\w+\] \[(\d+\.\d+)\] \[[^\]]+\]: (.*)$")
RE_PY = re.compile(r"^(\d+\.\d+) (.*)$")


class Seguidor:
    """Lê as linhas novas de um arquivo que ainda está sendo escrito."""

    def __init__(self, path):
        self.path, self.pos = Path(path), 0

    def novas(self):
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8", errors="replace") as f:
            f.seek(self.pos)
            linhas = []
            while True:
                linha = f.readline()
                if not linha.endswith("\n"):
                    break
                self.pos = f.tell()
                linhas.append(linha.rstrip("\n"))
            return linhas


def nome(tipo, n):
    return f"timer{n}" if tipo == "timer" else n


def main():
    no, script, saida = Seguidor(sys.argv[1]), Seguidor(sys.argv[2]), Path(sys.argv[3])
    out = saida.open("w", encoding="utf-8")
    out.write("evento,nome,inicio_ms,fim_ms\n")

    epoch = None           # horário (s) do envio do 1º lote = instante 0
    lote1, lote2 = [], []  # nomes enviados antes e depois dos 'delay'
    inicio = {}            # nome -> lista de inícios ainda sem fim
    terminou = False

    def emitir(ev, n, a, b):
        out.write(f"{ev},{n},{a:.1f},{b:.1f}\n")
        out.flush()

    def ms(t):
        return (t - epoch) * 1000

    while not terminou:
        for linha in script.novas():
            if linha.startswith("Callback sending order"):
                seq = linha.split(":", 1)[1].split()
                corte = seq.index("delay") if "delay" in seq else len(seq)
                lote1 = seq[:corte]
                lote2 = [s for s in seq[corte:] if s != "delay"]
            elif linha.startswith("Callback execution order"):
                terminou = True
            m = RE_PY.match(linha)
            if not m:
                continue
            t, msg = float(m.group(1)), m.group(2)
            if msg == "Sending callbacks" and epoch is None:
                epoch = t
                out.write(f"epoch,T0,{epoch * 1000:.1f},{epoch * 1000:.1f}\n")
                emitir("arrive", "high", 0, 0)  # mensagem inicial dos autores (300 ms)
                for n in lote1:
                    emitir("arrive", n, 0, 0)
            elif msg == "Processing sent callbacks" and epoch is not None:
                for n in lote2:
                    emitir("arrive", n, ms(t), ms(t))

        # o log do nó só é lido depois de conhecido o instante 0
        for linha in (no.novas() if epoch is not None else []):
            m = RE_ROS.match(linha)
            if not m:
                continue
            t, msg = float(m.group(1)), m.group(2)
            if (r := re.match(r"Setting up timer #(\d+) in (\d+) ms", msg)):
                venc = t + int(r.group(2)) / 1000
                emitir("arrive", f"timer{r.group(1)}", ms(venc), ms(venc))
            elif (r := re.match(r"Received (\w+) on (\w+)", msg)):
                n = nome(r.group(1), r.group(2))
                inicio.setdefault(n, []).append(t)
                emitir("start", n, ms(t), ms(t))
            elif (r := re.match(r"Finished (\w+) on (\w+)", msg)):
                n = nome(r.group(1), r.group(2))
                if inicio.get(n):
                    emitir("run", n, ms(inicio[n].pop(0)), ms(t))
        time.sleep(0.02)

    # lê o que sobrou do log do nó (a última callback termina junto com o script)
    time.sleep(0.3)
    for linha in no.novas():
        m = RE_ROS.match(linha)
        if m and (r := re.match(r"Finished (\w+) on (\w+)", m.group(2))):
            n = nome(r.group(1), r.group(2))
            if inicio.get(n):
                emitir("run", n, ms(inicio[n].pop(0)), ms(float(m.group(1))))

    out.close()


if __name__ == "__main__":
    main()
