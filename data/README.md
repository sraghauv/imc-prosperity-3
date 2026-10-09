# Data

IMC's released data bottles for Prosperity 3, renamed from `round-N-island-data-bottle` to
`roundN`. Redistributed here so the research scripts and figures reproduce without a download.

The backtester ships its own copy of this data — you do **not** need these files to run
`prosperity3bt`. They are for the scripts in [`../research/`](../research).

```
data/round1/   days -2, -1, 0    RAINFOREST_RESIN, KELP, SQUID_INK
data/round2/   days -1, 0, 1     + CROISSANTS, JAMS, DJEMBES, PICNIC_BASKET1/2
data/round4/   days 1, 2, 3      all 15 products, + observations_*.csv
data/round5/   days 2, 3, 4      all 15 products, trades de-anonymised
```

There is no `round3/` — that bottle was not kept. `round4/` contains `VOLCANIC_ROCK` and all five
vouchers, so the round-3 options analysis runs off the round-4 files.

## Formats

**`prices_round_N_day_D.csv`** — semicolon-separated, three book levels per side:

```
day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss
0;0;RAINFOREST_RESIN;9998;1;9995;30;;;10005;30;;;;;10001.5;0.0
```

Empty fields mean that level does not exist. `timestamp` advances in steps of 100.

**`trades_round_N_day_D.csv`** — semicolon-separated:

```
timestamp;buyer;seller;symbol;currency;price;quantity
```

`buyer` and `seller` are empty in rounds 1–4. In round 5 they carry real bot names — see
[round 5](../rounds/round-5.md).

**`observations_round_4_day_D.csv`** — **comma**-separated (the one file that differs), the
macaron conversion feed:

```
timestamp,bidPrice,askPrice,transportFees,exportTariff,importTariff,sugarPrice,sunlightIndex
0,627.0,628.5,1.0,9.0,-3.0,200.0,60.0
```

`bidPrice`/`askPrice` are the off-exchange conversion facility's quotes; tariffs can be negative
(a subsidy). See [round 4](../rounds/round-4.md).

## Stitching days together

Days are separate files with timestamps restarting at 0. Every script here builds one continuous
axis the same way:

```python
global_time = (df["day"] - df["day"].min()) * 1_000_000 + df["timestamp"]
```
