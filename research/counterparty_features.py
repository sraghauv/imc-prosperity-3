feature_extractor.py

#!/usr/bin/env python3
import pandas as pd
import argparse
import os
import sys

def compute_metrics(df, mid_df=None):
    total_trades    = len(df)
    avg_trade_size  = df['quantity'].mean()
    std_trade_size  = df['quantity'].std(ddof=0)
    unique_symbols  = df['symbol'].nunique()
    metrics = {
        'total_trades':      total_trades,
        'avg_trade_size':    avg_trade_size,
        'std_trade_size':    std_trade_size,
        'unique_symbols':    unique_symbols
    }
    if mid_df is not None:
        merged = pd.merge(df, mid_df, on=['timestamp','symbol'], how='inner')
        merged['abs_dev'] = (merged['price'] - merged['mid_price']).abs()
        metrics['avg_price_vs_mid'] = merged['abs_dev'].mean()
    return metrics

def main():
    p = argparse.ArgumentParser(
        description="Compute fingerprint metrics for one or more trade CSVs"
    )
    p.add_argument(
        "trades_csv",
        nargs="+",
        help="Paths to trade CSV(s) (semicolon‑delimited with timestamp;symbol;price;quantity;…)”"
    )
    p.add_argument(
        "--mid_csv",
        help="Optional mid‑price CSV (timestamp;symbol;mid_price)",
        default=None
    )
    args = p.parse_args()

    mid_df = None
    if args.mid_csv:
        if not os.path.isfile(args.mid_csv):
            print(f"Mid‑price file not found: {args.mid_csv}", file=sys.stderr)
            sys.exit(1)
        mid_df = pd.read_csv(args.mid_csv, sep=';')

    for path in args.trades_csv:
        if not os.path.isfile(path):
            print(f"Trade file not found: {path}", file=sys.stderr)
            continue

        df = pd.read_csv(path, sep=';')
        df['time'] = pd.to_datetime(df['timestamp'], unit='s')
        metrics = compute_metrics(df, mid_df)

        name = os.path.splitext(os.path.basename(path))[0]
        print(f"\n=== {name} ===")
        for k, v in metrics.items():
            print(f"{k:20s}: {v}")

if __name__ == "__main__":
    main()
