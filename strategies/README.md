# Strategies

[`../trader.py`](../trader.py) is the final submission. Everything here is a variant that led to
it or an alternative we kept: single-product prototypes where an idea was isolated, and two
near-complete traders that took different bets.

Each file is a self-contained `Trader` class and can be backtested directly:

```bash
prosperity3bt strategies/round2_basket_arbitrage.py 2 --out run.log
```

(The backtester resolves `from datamodel import ...` against the repo root, so run it from there.)

## Round 1 — market making

| File | Scope | What it isolates |
| --- | --- | --- |
| `round1_resin_market_maker.py` | `RAINFOREST_RESIN` | Static fair value of 10,000 with iceberg replenishment — visible clip of 5, remainder requeued next tick |
| `round1_resin_moving_average.py` | `RAINFOREST_RESIN` | MA fair value plus the hard stop loss, the version that shipped |
| `round1_squid_ink_reversion.py` | `SQUID_INK` | Size-filtered mid with `reversion_beta = -0.25`, at a looser position cap of 15 |
| `round1_squid_ink_simple.py` | `SQUID_INK` | A single *positive* beta (0.2) on the raw mid — the simpler model, and the disagreement worth noting: positive beta trends, negative beta fades |

## Round 2 — baskets

| File | Scope | What it isolates |
| --- | --- | --- |
| `round2_basket_arbitrage.py` | Both baskets + round-1 products | The round-2 submission: full synthetic-book construction, swmid spreads, 45-tick z-scores |
| `round2_basket_arbitrage_single.py` | `PICNIC_BASKET1` only | Implied bid/ask computed inline rather than through the generic loop, with `zscore_threshold = 7` — a deliberately rare-trigger variant |
| `round2_position_control.py` | Both baskets | Generic skeleton with spread means left at 0.0; useful as the untuned baseline |
| `basket_params.json` | — | An early calibration (both means 0.0, thresholds 2.0/2.5, targets 30). Not loaded at runtime — `trader.py` builds its params in `__init__` |

## Round 3 — vouchers

| File | Scope | What it isolates |
| --- | --- | --- |
| `round3_voucher_vol_trading.py` | Rock + 5 vouchers | First working version: BS pricing, bisection IV, per-strike IV z-scores |
| `round3_voucher_vol_delta_hedged.py` | Rounds 1–3 | Adds the delta hedge and merges the earlier rounds in. Direct predecessor of `trader.py` — differs only in the macaron block and in which strikes are disabled |

## Round 5 — counterparties

| File | Scope | What it isolates |
| --- | --- | --- |
| `round5_counterparty_aware_resin.py` | `RAINFOREST_RESIN` | The only strategy here that conditions on counterparty identity: running PnL against one named bot drives the quote width, and his public trades get mirrored |

## Alternative full trader

| File | Scope | What it isolates |
| --- | --- | --- |
| `all_rounds_alt_trader.py` | All 15 products | A parallel implementation of the whole competition, developed alongside `trader.py` |

Where it differs from the submission:

- **A counterparty flow throttle on `VOLCANIC_ROCK`** — if any single counterparty pushes 200+
  units through us in one tick, widths are halved and the effective position limit is boosted
  1.5×. Nameless, and therefore much harder to overfit than the Gary rule above.
- Basket targets of 60/50 rather than 60/100.
- Otherwise the same architecture: take→clear→make, the same reversion betas, BS vouchers with a
  delta hedge, and the same cost-based macaron model.
