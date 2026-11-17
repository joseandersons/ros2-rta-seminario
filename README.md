# Seminário STR: Response-Time Analysis of ROS 2 Processing Chains

Seminário da disciplina **Sistemas de Tempo Real** (UFAL) sobre o artigo:

> D. Casini, T. Blaß, I. Lütkebohle e B. B. Brandenburg. *Response-Time Analysis of ROS 2 Processing Chains Under Reservation-Based Scheduling*. ECRTS 2019. DOI: [10.4230/LIPIcs.ECRTS.2019.6](https://doi.org/10.4230/LIPIcs.ECRTS.2019.6)

Dupla: Vinícius Rafael e José Anderson.

## Conteúdo

| Pasta | O que tem |
|---|---|
| [`slides/`](slides/) | Slides da apresentação (30 min) |
| [`demo/rta/`](demo/rta/) | Calculadora em Python da análise de tempo de resposta do artigo (Lemas 2–8) |
| [`demo/ros2_ws/`](demo/ros2_ws/) | Nó ROS 2 que reproduz o experimento de validação do executor (Fig. 3 do artigo) |
| [`demo/gantt.py`](demo/gantt.py) | Gera o diagrama de Gantt a partir do trace do nó ROS 2 |

Instruções de execução: [`demo/README.md`](demo/README.md).

## Início rápido

```bash
pip install matplotlib
python demo/rta/rta_ros2.py --plot
```

## Referências

- Código original dos autores: https://github.com/boschresearch/ros2_response_time_analysis
- Documentação do ROS 2 Jazzy: https://docs.ros.org/en/jazzy/
