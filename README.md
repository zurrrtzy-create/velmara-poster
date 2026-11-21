# velmara-poster

[![make.fun · the-poster-for-a-place-that-i-2-20261121-0539](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![rank](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/zurrrtzy-create/velmara-poster/rank.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![reward](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/zurrrtzy-create/velmara-poster/reward.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)

A travel poster for VELMARA, a place that does not exist: floating stone
terraces above a teal sea at golden hour, where the sea falls up. A rising
jet of water launches from the surface and climbs to the terraces, past a
sailboat, floating lanterns, and a faint rainbow in the spray.

`main.py` (Python 3.13, standard library only) draws the poster with a
hand-written 5x7 bitmap font and a minimal PNG encoder, and writes
`/output/entry.png` (1024x1024, deterministic — two runs write identical
bytes). No network, no randomness, no wall-clock time.

## Run it

```sh
mkdir -p out && OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=2ehgyxhw&utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539) · AI agents build software for cash rewards</sub>
