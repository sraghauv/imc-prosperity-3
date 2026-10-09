#!/usr/bin/env python3
import sys

import pandas as pd
import matplotlib.pyplot as plt

def visualize_volcanic_trades(csv_path: str):
    # 1) Load CSV
    df = pd.read_csv(csv_path, sep=';')
    
    # 2) Filter volcanic rock
    vr = df[df['product'] == 'VOLCANIC_ROCK'].copy()
    if vr.empty:
        print("No VOLCANIC_ROCK trades found in the data.")
        return
    
    # 3) Compute a simple time axis (e.g. seconds since day 0)
    #    Adjust if you have real timestamps or multiple days
    vr['time_s'] = vr['day'] * 24 * 3600 + vr['timestamp']
    vr = vr.sort_values('time_s')
    
    # 4) (Optional) compute bid-ask spread
    vr['spread'] = vr['ask_price_1'] - vr['bid_price_1']
    
    # 5) Plot mid-price
    plt.figure()
    plt.plot(vr['time_s'], vr['mid_price'], marker='o')
    plt.xlabel('Time (s)')
    plt.ylabel('Mid Price')
    plt.title('VOLCANIC_ROCK Mid Price over Time')
    plt.grid(True)
    
    # 6) Plot spread
    plt.figure()
    plt.plot(vr['time_s'], vr['spread'], marker='x')
    plt.xlabel('Time (s)')
    plt.ylabel('Bid–Ask Spread')
    plt.title('VOLCANIC_ROCK Bid–Ask Spread over Time')
    plt.grid(True)
    
    plt.show()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python visualize_volcanic_trades.py <data.csv>")
        sys.exit(1)
    visualize_volcanic_trades(sys.argv[1])
