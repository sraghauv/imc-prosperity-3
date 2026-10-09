# Research

Offline analysis. None of this runs inside the algorithm — it is where the algorithm's constants
came from. Run everything from the repo root, so the `data/` paths resolve.

```bash
pip install -r requirements.txt
```

## Parameter fitting

| Script | Produces | Used by |
| --- | --- | --- |
| `find_critical_sunlight_index.py` | `CSI = 28.22` — sweeps sunlight-index percentiles and picks the threshold maximising the price gap between the below/above regimes | [Round 4](../rounds/round-4.md) |
| `model_basket_spread.py` | `default_spread_mean` = −38.2 (basket 1) and 76.0 (basket 2) — basket-minus-synthetic spread per day | [Round 2](../rounds/round-2.md) |
| `analyze_spread.py` | Spread diagnostics across days | [Round 2](../rounds/round-2.md) |

```bash
python research/find_critical_sunlight_index.py
python research/model_basket_spread.py
```

## Counterparty tooling (round 5)

| Script | What it does |
| --- | --- |
| `split_trades_by_counterparty.py` | Fans the de-anonymised trade history into one CSV per name, counting each trade for **both** the buyer and the seller |
| `list_counterparties.py` | Unique buyer/seller names in a trade file |
| `counterparty_features.py` | Per-counterparty fingerprint: trade-size mean and standard deviation, and average deviation from the prevailing mid — the number that separates liquidity-seekers from informed flow |
| `plot_counterparty_volume.py` | Daily volume per counterparty, total and split by product |

```bash
python research/split_trades_by_counterparty.py data/round5/trades_round_5_day_*.csv --outdir by_name
python research/counterparty_features.py
python research/plot_counterparty_volume.py by_name/Gary.csv
```

## Plots and notebooks

| File | What it shows |
| --- | --- |
| `notebooks/price_explorer.ipynb` | Stitches the three round-1 days into one continuous time axis (`global_time = day × 1e6 + timestamp`) and plots one product's mid price |
| `plot_volcanic_rock.py` | Rock mid price and bid/ask spread over time |

```bash
python research/plot_volcanic_rock.py data/round4/prices_round_4_day_1.csv
```

The figures in [`../assets/`](../assets) used by the writeups are regenerated from `data/` with
the same conventions.

## Parameter sweeps — `grid_search/`

All four wrap the backtester: substitute parameters into a trader template, shell out to
`prosperity3bt`, scrape the final `profit_and_loss` out of the activity log, rank.

| Script | Sweeps | Size |
| --- | --- | --- |
| `sweep_kelp.py` | `prevent_adverse` × `adverse_volume` (10–40) × `reversion_beta` (0.10–0.40) | 98 runs |
| `sweep_baskets.py` | Both baskets' z-thresholds, windows and target positions, plus constituent params | 8-dimensional Cartesian product |
| `sweep_market_maker.py` | Generic `fair_value` × `take_width` × `clear_width` × `default_edge` template | 18 runs |
| `rank_sweep_results.py` | Parses the captured stdout log, filters to runs above a profit threshold, ranks | — |

```python
# the parsing contract every sweep relies on
activities = log.split("Activities log:")[1].split("Trade History:")[0]
df = pd.read_csv(io.StringIO(activities), sep=";")
pnl = df["profit_and_loss"].iloc[-1]
```

**Caveat on `kelp_sweep_combos.json`:** the sweep records each combination but never writes the
PnL field into the JSON, so that file is a list of what was tried, not a ranking. The profit
numbers only ever existed in the captured stdout — which is what `rank_sweep_results.py` reads.
The shipped `reversion_beta = -0.229` came from that log.
