# Seminário STR: Response-Time Analysis of ROS 2 Processing Chains

Seminário da disciplina **Sistemas de Tempo Real** (UFAL) sobre o artigo:

> D. Casini, T. Blaß, I. Lütkebohle e B. B. Brandenburg. *Response-Time Analysis of ROS 2 Processing Chains Under Reservation-Based Scheduling*. ECRTS 2019. DOI: [10.4230/LIPIcs.ECRTS.2019.6](https://doi.org/10.4230/LIPIcs.ECRTS.2019.6)

Dupla: Vinícius Rafael e José Anderson.

## Conteúdo

| Pasta | O que tem |
|---|---|
| [`slides/`](slides/) | Slides da apresentação (30 min): link, fonte e roteiro |
| [`artefatos/`](artefatos/) | Material de apoio: resumo do artigo, situação atual e análise do executor no Jazzy |
| [`original/`](original/) | **Demo:** o código original dos autores (experimento da Fig. 3) rodando no ROS 2 Jazzy, com gráfico ao vivo |

Instruções de execução: [`original/README.md`](original/README.md).

## Início rápido

No Ubuntu (WSL) com o ROS 2 Jazzy instalado:

```bash
bash ~/ros2-rta-seminario/original/ao_vivo.sh
```

## Referências

- Código original dos autores: https://github.com/boschresearch/ros2_response_time_analysis
- Documentação do ROS 2 Jazzy: https://docs.ros.org/en/jazzy/
