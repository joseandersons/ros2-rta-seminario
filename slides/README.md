# Slides

A apresentação (21 slides, com notas do apresentador) está no claude.ai:
https://claude.ai/artifact/C6cRoy8i63BAKHB3GSnhr7

- Para apresentar: abra o link e use o modo de apresentação.
- Para baixar em PowerPoint ou PDF: menu **Share › Export** na página da apresentação. Coloque o arquivo exportado nesta pasta.

## Fonte

A pasta [`fonte/`](fonte/) guarda uma cópia do código dos slides:

- `deck.json`: título, ordem dos slides e fontes;
- `deck.css`: estilo compartilhado;
- `slides/<id>.html`: um arquivo por slide, com as notas do apresentador no `<aside>` final.

As imagens (`/_blob/...`) ficam guardadas na própria apresentação. Os originais estão em `demo/rta/sweep.png` e `demo/results/`.

## Roteiro (30 min)

| Tempo | Bloco |
|---|---|
| 3 min | Motivação: robótica, ROS e garantias de tempo |
| 6 min | Executor ROS 2, polling points e a Fig. 3 (inversão de prioridade) |
| 5 min | Reservas (CBS / SCHED_DEADLINE) e o modelo em DAG |
| 6 min | Análise: Lemas 2–4, Eq. 6 e cadeias (ligação com a RTA da aula) |
| 3 min | Estudo de caso move_base (Fig. 8) |
| 4 min | Demonstração |
| 3 min | Situação atual, crítica e conclusões |
