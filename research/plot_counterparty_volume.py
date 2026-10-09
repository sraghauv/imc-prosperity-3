#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

def main():
    p = argparse.ArgumentParser(
        description="Plot per‑commodity time series + overall volume for one trader"
    )
    p.add_argument("trader_csv",
                   help="Path to the per‑trader CSV (semicolon‑delimited)")
    p.add_argument("-o", "--outdir",
                   default="plots_png",
                   help="Directory to save PNG files")
    args = p.parse_args()

    # 1) LOAD
    df = pd.read_csv(args.trader_csv, delimiter=';')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)

    # Extract a clean name for files
    trader_name = os.path.splitext(os.path.basename(args.trader_csv))[0]
    os.makedirs(args.outdir, exist_ok=True)

    # 2) AGGREGATE
    daily = (df
             .groupby('symbol')
             .resample('D')['quantity']
             .sum()
             .unstack('symbol')
             .fillna(0))
    total_volume = daily.sum(axis=1)

    # choose distinct colors
    cmap = plt.get_cmap('tab20', len(daily.columns))

    # 3a) Plot per‑commodity quantities
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    for idx, symbol in enumerate(daily.columns):
        ax1.plot(daily.index, daily[symbol], label=symbol, color=cmap(idx))
    ax1.set_ylabel("Quantity")
    ax1.set_title(f"Daily Quantity by Commodity — {trader_name}")
    ax1.legend(loc='upper left', fontsize='small')
    fig1.tight_layout()
    out1 = os.path.join(args.outdir, f"{trader_name}_by_commodity.png")
    fig1.savefig(out1)
    plt.close(fig1)

    # 3b) Plot total daily volume
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.plot(total_volume.index, total_volume.values, color='C0')
    ax2.set_ylabel("Total Quantity")
    ax2.set_title(f"Total Daily Trade Volume — {trader_name}")
    ax2.set_xlabel("Date")
    fig2.tight_layout()
    out2 = os.path.join(args.outdir, f"{trader_name}_total_volume.png")
    fig2.savefig(out2)
    plt.close(fig2)

    print(f"Saved:\n  • {out1}\n  • {out2}")

if __name__ == "__main__":
    main()
