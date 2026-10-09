# IMC Prosperity 3 — Algorithmic Trading

**59th of 12,500+ teams worldwide (top 0.5%) · 64th in algorithmic trading**

![placement](https://img.shields.io/badge/global%20rank-59%20%2F%2012%2C500%2B-2563eb)
![algo rank](https://img.shields.io/badge/algorithmic%20trading-64th-0891b2)
![products](https://img.shields.io/badge/products%20traded-15-16a34a)
![python](https://img.shields.io/badge/python-3.9%2B-9333ea)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

Our team's algorithm for [IMC Prosperity 3](https://prosperity.imc.com/) (2025), a five-round
algorithmic trading competition. Each round adds new products to a simulated exchange; you submit
a Python class that receives an order book every 100 ms and returns orders, and it trades against
IMC's bots for a week before the next round unlocks.

This repository is the cleaned-up, documented version of our working repo: one submitted
algorithm, the strategy variants behind it, the research scripts that produced its parameters,
and **a writeup per round explaining what the round asked for and what we did about it**.

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

## Layout

```
trader.py                  final submission — all 15 products
datamodel.py               competition-provided types (Order, OrderDepth, TradingState, …)

rounds/                    ← the writeups: one per round, start here
strategies/                the variants behind the submission (see strategies/README.md)
research/                  offline analysis: CSI fit, spread model, counterparty tooling, plots
research/grid_search/      parameter sweeps that wrap the backtester
data/                      IMC's data bottles, renamed to data/round{1,2,4,5}
assets/                    figures used by the writeups, generated from data/
```

## What we'd change next

This is the code as submitted, not a cleaned-up retelling of it. Six things we would take on
first if the competition ran again — documented here because the reasoning is more useful than a
silent patch would be.

- **Complete the basket hedge.** `convert_synthetic_basket_orders` excludes `CROISSANTS` when
  translating the synthetic leg into real orders, so basket 1 is hedged with only `JAMS` and
  `DJEMBES` and carries roughly half its weight unhedged. Croissants were dropped from the leg
  set mid-competition, which solved the immediate problem by moving it onto the remaining legs
  rather than removing it. ([round 2](rounds/round-2.md#execution-and-hedging))
- **Make time to expiry actually count down.** `_calc_time_to_expiry` reads
  `getattr(state, "current_round", 1)`, and the standard `TradingState` has no such attribute, so
  it always resolves to round 1 and `T = 7/250`. The IV *level* is therefore biased — z-scoring
  IV against its own recent history absorbs much of a constant bias, which is why this survived
  as long as it did, but the options decay and the model does not know it.
- **Reject failed implied-vol solves instead of trusting them.** When a deep in-the-money
  voucher's mid sits below intrinsic value, no volatility reproduces the quote and the bisection
  pins to its lower bound. Offline that is 8.9% of solves; live, the bot feeds those near-zero
  values straight into the voucher's IV history and z-scores against them. Clamping on the bound
  should mean "no observation", not "vol is zero". ([round 3](rounds/round-3.md#pricing))
- **Fix the rock mid to use the best quotes.** The hedge computes
  `(min(buy_orders) + max(sell_orders)) / 2` — the *worst* bid and *worst* ask — where
  `(max(buy_orders) + min(sell_orders)) / 2` was intended. It is symmetric, so it costs the hedge
  precision rather than direction, but it is wrong on every tick.
- **Arbitrate the rock position between its three signals.** The delta hedge, a 5% stop loss and
  a 15-tick reversion overlay all append to the same order list, so the net position is their sum
  rather than a prioritised decision. The hedge should win; today it merely votes.
- **Persist the sweep results.** `research/grid_search/sweep_kelp.py` appends each combination to
  JSON without the PnL field, so `kelp_sweep_combos.json` records what was tried rather than what
  won, and the ranking only exists in captured stdout that `rank_sweep_results.py` has to
  re-parse. ([round 1](rounds/round-1.md#parameter-fitting))

## Credits

Built by a five-person team over the five weeks of the competition, finishing **59th of 12,500+
teams (top 0.5%)** and **64th in the algorithmic trading category**. The per-round structure of
this repo follows how the work actually happened: each round, a new product class, a parameter
fit, a merge into the shared trader.

Market data under `data/` is IMC Trading's, redistributed for reproducibility. Code is
[MIT](LICENSE).
