# Backtest results

Every number on this page was produced by running the committed [`trader.py`](../trader.py)
through the community backtester
([`prosperity3bt`](https://github.com/jmerle/imc-prosperity-3-backtester)) against IMC's released
data. Reproduce any of it with one command:

```bash
prosperity3bt trader.py 5 --no-out      # all three days of round-5 data
prosperity3bt trader.py 5-4 --no-out    # a single day
```

These are **backtest** figures in seashells, not competition placings.

## By round

The backtester runs the days belonging to the round you ask for, so each row is the submitted
algorithm against progressively later data with progressively more products live.

| Round data | Days | Products live | Per-day PnL | **Total** |
| --- | --- | --- | --- | --- |
| Round 1 | −2, −1, 0 | 3 | 20,343 · 21,023 · 18,587 | **59,953** |
| Round 2 | −1, 0, 1 | 8 | 94,821 · 66,813 · 41,912 | **203,546** |
| Round 3 | 0, 1, 2 | 14 | 85,262 · 77,376 · 272,554 | **435,192** |
| Round 4 | 1, 2, 3 | 15 | 72,494 · 271,200 · 207,105 | **550,798** |
| **Round 5** | 2, 3, 4 | 15 | 271,200 · 207,105 · 310,761 | **789,066** |

Round 5 days 2 and 3 are the same market days as round 4 days 2 and 3 and reproduce to the
seashell, which is a useful consistency check on the run.

## Round 5, by product

Summed across the three days — total **789,063** (the three-seashell gap against the table above
is per-day rounding in the backtester's own display).

| Product | PnL | Share of gross |
| --- | --- | --- |
| `VOLCANIC_ROCK_VOUCHER_10000` | **+468,658** | 55% |
| `VOLCANIC_ROCK_VOUCHER_9750` | +124,747 | 15% |
| `RAINFOREST_RESIN` | +83,673 | 10% |
| `VOLCANIC_ROCK` | +82,136 | 10% |
| `PICNIC_BASKET1` | +46,044 | 5% |
| `PICNIC_BASKET2` | +17,728 | 2% |
| `KELP` | +15,097 | 2% |
| `DJEMBES` | +9,888 | 1% |
| `SQUID_INK` | +8,525 | 1% |
| `CROISSANTS` | 0 | never traded |
| `VOUCHER_9500`, `VOUCHER_10250` | 0 | position limit 0 |
| `VOLCANIC_ROCK_VOUCHER_10500` | **−8,626** | |
| `MAGNIFICENT_MACARONS` | **−12,985** | |
| `JAMS` | **−45,822** | |

Best single day: **round 5 day 4, +310,761**, with `VOUCHER_10000` at +167,548 and `VOUCHER_9750`
at +54,863.

## What the numbers say

**One instrument carries the book.** The at-the-money voucher alone is 55% of gross PnL, and the
two live near-the-money strikes together are 70%. The implied-vol z-score strategy on
`VOUCHER_10000` is the highest-conviction thing in this repo — and the concentration is itself the
biggest risk in it. One strike, one model, one parameter pair.

**The far wing loses.** `VOUCHER_10500` is the one live voucher that is negative (−8,626). Its
z-score threshold was raised to 2.0 precisely because wing IV is noisy, and it still was not
enough. On this evidence the right call was to disable it alongside 9500 and 10250.

**Hedging the baskets costs more than the baskets make.** The two baskets earn +63,772 between
them, and the hedge legs give back −35,934 (`JAMS` −45,822, `DJEMBES` +9,888) — so the basket
complex nets about +27,838, with more than half the gross eaten by the replication. `CROISSANTS`
sits at exactly 0 because the final trader stopped trading it at all; see
[round 2](../rounds/round-2.md#execution-and-hedging) for why, and what that leaves unhedged.

**Resin is the dependable floor.** +83,673 across three days, consistent to within a few percent
day to day, from a constant fair value and wide quotes. It is the simplest strategy here and the
third most profitable, with none of the variance of the options book.

**Macarons never found their edge.** −12,985 net: positive on day 4 (+1,858) and negative before
that (−13,489 on the shared day 3). The cost model and the conversion arbitrage are sound ideas,
but the quoting layer wrapped around them lost more than they made.

**Squid ink earns in line with its leash.** +8,525 on a four-unit position cap is a good return on
the risk taken. It was never going to be a large number, and the cap is why it was never a large
loss either.

## Caveats

- **Backtest PnL overstates live performance.** The backtester fills our resting orders against
  historical book snapshots without modelling queue position or our own market impact — which
  flatters a market-making strategy more than any other kind.
- **These numbers are not the ones we saw during the competition.** The original 2025 run logs
  (~234 MB, not committed) show a lower total for the same final day: roughly +250,000 against
  the +310,761 reproduced here. The algorithm is unchanged; the backtester is not the same
  version it was in April 2025. The reproducible number is the one published above.
- Round 3 appears in the table even though `data/round3/` is absent from this repo — the
  backtester ships its own copy of every round's data.
