# IMC Prosperity 3 — Algorithmic Trading

Our team's algorithm for [IMC Prosperity 3](https://prosperity.imc.com/) (2025), a five-round
algorithmic trading competition. Each round adds new products to a simulated exchange; you submit
a Python class that receives an order book every 100 ms and returns orders, and it trades against
IMC's bots for a week before the next round unlocks.

This repository is the cleaned-up, documented version of our working repo: one submitted
algorithm, the strategy variants behind it, the research scripts that produced its parameters,
and **a writeup per round explaining what the round asked for and what we did about it**.

> **+789,066 seashells** across the three days of round-5 data, 15 products live —
> reproducible from this repo with a single command. Per-round and per-product breakdown in
> [`results/backtests.md`](results/backtests.md).

## The rounds

| | Round | Products added | Core idea |
| --- | --- | --- | --- |
| 1 | [**Market making**](rounds/round-1.md) | `RAINFOREST_RESIN`, `KELP`, `SQUID_INK` | Three products, three price regimes, one take→clear→make engine with adverse-selection-filtered fair values |
| 2 | [**Basket arbitrage**](rounds/round-2.md) | `CROISSANTS`, `JAMS`, `DJEMBES`, `PICNIC_BASKET1/2` | Baskets are replicable from their contents — trade the basket against a synthetic built in the component books, on a 45-tick spread z-score |
| 3 | [**Options**](rounds/round-3.md) | `VOLCANIC_ROCK` + 5 call vouchers | Black-Scholes, implied vol by bisection, per-strike IV z-scores, and a delta hedge back into the underlying |
| 4 | [**Conversions**](rounds/round-4.md) | `MAGNIFICENT_MACARONS` | Fair value built bottom-up from sugar price, tariffs and a fitted critical sunlight index; fee-inclusive arbitrage against the conversion facility |
| 5 | [**Counterparties**](rounds/round-5.md) | *none — the trade history is de-anonymised* | Fingerprinting named bots by their deviation from mid, and two prototypes for trading on who is on the other side |

## Quick start

```bash
git clone https://github.com/sraghauv/imc-prosperity-3.git
cd imc-prosperity-3
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# backtest the submitted algorithm against a round's data
prosperity3bt trader.py 5 --out run.log
```

[`prosperity3bt`](https://github.com/jmerle/imc-prosperity-3-backtester) is the community
backtester; it ships its own copy of IMC's round data and runs all days up to the round you pass.
The `data/` directory in this repo is the raw data bottles, used by the research scripts.

## What the submitted algorithm does

[`trader.py`](trader.py) is the final submission: a single `Trader.run(state)` covering all 15
products, with state persisted between ticks through `jsonpickle` (the engine only hands back an
opaque string, so price histories, spread histories and IV histories all round-trip through it).

```
                    ┌──────────────── TradingState (order books, own trades, observations)
                    ▼
    ┌───────────────────────────────────────────────────────────────────────┐
    │  per-product fair value                                              │
    │    resin    → MA(400) of mid, seeded at 10,000                       │
    │    kelp     → size-filtered mid × (1 + ret × −0.229)                 │
    │    squid    → size-filtered mid × (1 + ret × −0.250)                 │
    │    baskets  → swmid(basket) − swmid(synthetic)  → z-score vs 45-tick │
    │    vouchers → Black-Scholes IV (bisection)      → z-score vs 30-tick │
    │    macarons → sugar + tariffs, ×1.10 below CSI, − storage × position │
    └───────────────────────────────────────────────────────────────────────┘
                    ▼
    take (cross when mispriced) → clear (flatten inventory) → make (quote both sides)
                    ▼
    overlays: stop losses · iceberg slicing · delta hedge into VOLCANIC_ROCK · conversions
```

Three ideas do most of the work:

- **Trust size, not price.** Fair values for the drifting products are built only from book levels
  with real volume behind them, so a one-lot quote far from the market cannot drag our pricing.
- **Let position skew the quotes.** Resin uses a soft position limit, macarons subtract
  `position × storage_cost` from fair value. Both make the book itself push inventory toward flat,
  rather than relying on a separate unwind rule.
- **Size is a risk control, and a cheap one.** Squid ink is capped at 4 units against an exchange
  limit many times that; two of the five vouchers ship with a position limit of 0. Deciding what
  *not* to trade was worth more than most of the parameter tuning.

## Results

Running the committed `trader.py` against each round's data:

| Round data | Products live | Total PnL |
| --- | --- | --- |
| Round 1 | 3 | 59,953 |
| Round 2 | 8 | 203,546 |
| Round 3 | 14 | 435,192 |
| Round 4 | 15 | 550,798 |
| **Round 5** | 15 | **789,066** |

More than half of that comes from one instrument — the at-the-money volcanic rock voucher at
+468,658 over round 5. Resin is the steady floor (+83,673, barely varying day to day), the
baskets net about +27,838 after their hedge legs, and macarons lose −12,985. Honest breakdown,
including what loses money and why, in [`results/backtests.md`](results/backtests.md).

## Layout

```
trader.py                  final submission — all 15 products
datamodel.py               competition-provided types (Order, OrderDepth, TradingState, …)

rounds/                    ← the writeups: one per round, start here
results/backtests.md       PnL per run and per product, with caveats

strategies/                the variants behind the submission (see strategies/README.md)
research/                  offline analysis: CSI fit, spread model, counterparty tooling, plots
research/grid_search/      parameter sweeps that wrap the backtester
data/                      IMC's data bottles, renamed to data/round{1,2,4,5}
assets/                    figures used by the writeups, generated from data/
```

## Known quirks, left in on purpose

This is competition code written against a deadline. Rather than quietly fixing these, they are
documented — they are part of what the results were actually produced by.

- **The croissant hedge leg is skipped.** `convert_synthetic_basket_orders` excludes `CROISSANTS`
  when translating the synthetic leg into real orders, so basket 1 is hedged with only `JAMS` and
  `DJEMBES` and carries roughly half its weight unhedged. It was cut because it lost money as a
  hedge leg in round 2 (−9,057), but the problem only moved: `JAMS` now loses −45,822, eating
  most of the baskets' +63,772. ([round 2](rounds/round-2.md#execution-and-hedging))
- **Time to expiry is effectively frozen.** `_calc_time_to_expiry` reads
  `getattr(state, "current_round", 1)`, and the standard `TradingState` has no such attribute — so
  it always resolves to round 1 and `T = 7/250`. The IV *level* is therefore biased, though
  z-scoring IV against its own recent history absorbs much of a constant bias.
- **Failed implied-vol solves are treated as real observations.** When a deep in-the-money
  voucher's mid sits below intrinsic value, no volatility reproduces the quote and the bisection
  pins to its lower bound. Offline, that is 8.9% of solves; live, the bot feeds those near-zero
  values straight into the voucher's IV history and z-scores against them.
  ([round 3](rounds/round-3.md#pricing))
- **The rock mid uses the widest quotes, not the best.** The hedge computes
  `(min(buy_orders) + max(sell_orders)) / 2`, i.e. the worst bid and worst ask, where
  `(max(buy_orders) + min(sell_orders)) / 2` was intended. It is symmetric, so it degrades the
  hedge's precision more than its direction.
- **The kelp sweep never saved its PnL.** `research/grid_search/sweep_kelp.py` appends each
  combination to JSON without the PnL field, so `kelp_sweep_combos.json` records what was tried,
  not what won; the profit numbers only exist in the captured stdout that
  `rank_sweep_results.py` parses. ([round 1](rounds/round-1.md#parameter-fitting))
- **The rock position is shared between three signals.** The delta hedge, a 5% stop loss and a
  15-tick reversion overlay all append to the same order list, so the net rock position is their
  sum rather than a prioritised decision.

## Credits

Built by a five-person team over the five weeks of the competition. The per-round structure of
this repo follows how the work actually happened: each round, a new product class, a parameter
fit, a merge into the shared trader.

Market data under `data/` is IMC Trading's, redistributed for reproducibility. Code is
[MIT](LICENSE).
