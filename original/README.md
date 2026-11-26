# Código original dos autores no ROS 2 Jazzy

Esta pasta tem o experimento de validação do executor (Seção 3, Figura 3) **escrito pelos próprios autores do artigo**, tirado de
[boschresearch/ros2_response_time_analysis](https://github.com/boschresearch/ros2_response_time_analysis) (pasta `model_validation`, commit `8056fbd`, licença BSD-3-Clause, ver [`LICENSE`](LICENSE)).

A ideia é comparar o **mesmo código** em duas versões do ROS 2: o resultado no Crystal (2018) é o publicado no artigo; o resultado no Jazzy (2024) é o que obtivemos rodando o código deles, quase sem mudanças, no ROS 2 atual.

## O que precisou mudar

O código foi feito para o ROS 2 Crystal (2018). Para compilar no Jazzy foram só ajustes de API; a lógica do experimento é a mesma. Todas as mudanças estão marcadas com `[Jazzy]` no código, e o commit anterior a elas guarda a versão original intacta.

- `create_subscription` e `create_publisher` (C++ e Python) passaram a exigir o QoS; usamos `10`.
- `nextTimerId` não era inicializado no original; agora começa em `0`.
- `CMakeLists.txt`: a função `generate_interfaces()` usava `rosidl_target_interfaces`, que não existe mais; as interfaces são ligadas com `rosidl_get_typesupport_target`. C++14 virou C++17, exigido pelo rclcpp atual.

## Como rodar (Ubuntu/WSL com ROS 2 Jazzy)

**Ao vivo, com gráfico (para a apresentação):**

```bash
bash ~/ros2-rta-seminario/original/ao_vivo.sh
```

Compila o código dos autores, roda o experimento e abre uma janela que desenha as callbacks enquanto elas executam: o ▼ é a chegada, a linha tracejada é a espera e a barra cresce enquanto a callback roda. O código dos autores **não é alterado** para isso: o [`coletor.py`](coletor.py) só lê os logs que o próprio código deles já imprime (o nó registra "Received ..." e "Finished ..." com horário, e o script registra quando envia cada lote) e transforma em trace para a janela ([`live.py`](live.py)). A primeira barra curta do `high` (300 ms) é a mensagem de "aquecimento" que o script dos autores manda antes da rajada.

**Só a ordem, em texto:**

```bash
bash rodar.sh 3     # compila em ~/orig_ws e roda o experimento 3 vezes
```

O script dos autores (`send_cb_sequence`) manda a mesma sequência da Figura 3 (`low medium high srv_high srv_low` duas vezes, uma pausa e depois `srv_medium srv_medium high`, com timers em 200 ms e 2300 ms) e imprime a ordem em que as callbacks rodaram. Cada callback dura 500 ms.

## Resultado no Jazzy

Três execuções:

```
medium low high srv_high srv_low timer1 timer0 timer2 timer3 medium low high srv_medium srv_high srv_low high srv_medium
medium low high srv_high srv_low timer1 timer0 timer2 timer3 medium low high srv_medium srv_high srv_low high srv_medium
low medium high srv_low srv_high timer1 timer0 timer2 timer3 low medium high srv_low srv_medium srv_high high srv_medium
```

O que se vê, comparando com o resultado do artigo no Crystal:

1. **Espera pelo polling point continua.** `srv_medium` chega durante a janela e só roda numa janela seguinte; cada callback roda uma vez por janela (o segundo `low/medium/high` fica para depois).
2. **Timers agora esperam a janela.** Os timers 0 e 1 vencem em 200 ms, mas só rodam depois que as 5 callbacks da primeira janela terminam. No Crystal, o artigo mostra os timers furando a janela.
3. **A ordem dentro do tipo não segue mais o registro.** Os subscribers foram registrados como `high, medium, low`, mas rodaram `medium low high` ou `low medium high`, e a ordem varia entre execuções. O mesmo vale para os services.
4. **A ordem entre tipos continua:** timers, depois subscribers, depois services.

Conclusão: o mesmo código dos autores se comporta de forma diferente no ROS 2 de hoje em dois pontos (timers e ordem dentro do tipo), enquanto a espera pelo polling point continua igual.
