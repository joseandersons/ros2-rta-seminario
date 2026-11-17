# Demo do seminário: RTA de cadeias ROS 2 (Casini et al., ECRTS 2019)

São duas demonstrações independentes:

| Parte | O que mostra | Precisa de |
|---|---|---|
| `rta/rta_ros2.py` | As equações do artigo (Lemas 2–8) aplicadas a um exemplo: tempos de resposta, latência da cadeia e varredura do orçamento da reserva (como a Fig. 8a) | Só Python (+ matplotlib para o gráfico) |
| `ros2_ws/` + `gantt.py` | O experimento de validação da Seção 3 (Fig. 3) rodando num **ROS 2 atual**, para responder "o comportamento de 2018 continua válido?" | Linux/WSL2 com ROS 2 Jazzy |

---

## Parte 1: calculadora de RTA (roda no Windows)

```bash
cd rta
python rta_ros2.py --plot
```

O que apontar na apresentação:

1. **Prioridade não adianta para subscribers.** Compare as colunas `R ideal` (prioridade fixa não preemptiva, como na aula) e `R ROS 2`. `s_filtro` é a subscriber de maior prioridade, mas no ROS 2 sofre interferência de *todas* as outras callbacks (Eq. 6). Por isso seu R sobe de 74 para 199 ms.
2. **Timers não mudam:** eles não dependem de polling points (Lema 3), então os dois valores são iguais.
3. **Análise holística vs. soma** (Seção 5.4): 104 ms contra 441 ms. Somar os R individuais conta as rajadas várias vezes ("pay burst only once").
4. **Dimensionamento da reserva:** abaixo de 50% de banda a análise não converge. Acima disso, a latência cai, como na Fig. 8a do artigo.

Ligação com as aulas:
- A iteração `sbf(A+R) >= demanda(R)` é a **mesma RTA da aula** (`R = C + Σ⌈R/T⌉C`), com `sbf` no lugar de `t`.
- O bloqueio `B = max e` de prioridade menor é o bloqueio de escalonamento **não preemptivo**.

Para mudar o exemplo, edite `example_system()`. A lista está em ordem de prioridade: timers primeiro, depois subscribers na ordem de registro.

---

## Parte 2: experimento no ROS 2 real (Linux)

### Instalação (uma vez, no Windows)

1. No PowerShell **como administrador**, instale o WSL2 com Ubuntu 24.04 e reinicie:
   ```
   wsl --install -d Ubuntu-24.04
   ```
2. No Ubuntu, instale o ROS 2 Jazzy seguindo o guia oficial: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html (pacote `ros-jazzy-ros-base` + `ros-dev-tools`).

### Compilar e rodar

No terminal do Ubuntu (a pasta do Windows aparece em `/mnt/c/...`):

```bash
source /opt/ros/jazzy/setup.bash
cp -r <pasta-do-repo>/demo/ros2_ws ~/
cd ~/ros2_ws
colcon build
source install/setup.bash

ros2 run polling_demo polling_demo single   # executor single-threaded (o do artigo)
ros2 run polling_demo polling_demo events   # EventsExecutor (mais novo), para comparar
ros2 run polling_demo polling_demo multi    # MultiThreadedExecutor
```

Cada execução leva ~10 s e gera `trace_<executor>.csv` na pasta atual. Copie os CSVs de volta para o Windows e gere o Gantt:

```bash
cp trace_*.csv <pasta-do-repo>/demo/
```

```bash
python gantt.py trace_single.csv
```

### O que o experimento faz (igual à Seção 3 do artigo)

- O nó sob teste tem subscribers `H, M, L`, services `SH, SM, SL` (registrados nessa ordem) e 4 timers one-shot (`t0, t1` em 200 ms e `t2, t3` em 2300 ms). Cada callback ocupa a CPU por 500 ms.
- Em t = 0 chegam `<L M H SH SL L M H SH SL>`. Em t = 1500 ms chegam `<SM SM H>`.

### O que procurar no Gantt (compare com a Fig. 3 do artigo)

1. **Uma instância por janela:** com duas mensagens `H` na fila, só uma executa por janela de processamento.
2. **Polling point:** `SM` chega em 1500 ms, mas só executa depois que a janela atual esvazia.
3. **Ordem de prioridade:** timers, depois subscribers, services e clients; dentro de cada tipo, a ordem de registro.
4. **Timers furam o polling point?** No Crystal (2018), sim. **Se no Jazzy for diferente, isso é um resultado do seminário**: o modelo do artigo envelheceu e os trabalhos posteriores tiveram de revisá-lo.
5. **`events` vs `single`:** o EventsExecutor usa uma fila de eventos em vez do readySet. Vejam se as duas mensagens `H` passam a rodar seguidas e se a ordem muda para FIFO.

### Limitações (digam na apresentação)

- WSL2 é uma VM e o kernel não é PREEMPT_RT, então os tempos têm ruído de milissegundos. O que importa é a **ordem** de execução, não os tempos exatos.
- No `multi`, as callbacks do nó caem no mesmo callback group mutuamente exclusivo (padrão), então continuam serializadas.
- O código ROS 2 foi escrito para o Jazzy, mas não foi compilado aqui (a máquina não tinha WSL nem Docker). Se der erro de compilação, o mais provável é a parte do EventsExecutor: comentem o bloco `#if __has_include(...)`.
