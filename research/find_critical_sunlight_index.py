import glob
import pandas as pd
import numpy as np

# 1. Load and clean data (observations)
obs_files = sorted(glob.glob('data/round4/observations_round_4_day_*.csv'))
obs_df = pd.concat([pd.read_csv(f, sep=',') for f in obs_files], ignore_index=True)
obs_df.columns = obs_df.columns.str.strip()
obs_df['timestamp'] = pd.to_numeric(obs_df['timestamp'], errors='coerce')
obs_df = obs_df.dropna(subset=['timestamp', 'sunlightIndex'])

# 2. Load and clean price data for MAGNIFICENT_MACARONS
price_files = sorted(glob.glob('data/round4/prices_round_4_day_*.csv'))
price_frames = []
for f in price_files:
    df = pd.read_csv(f, sep=';')
    df.columns = df.columns.str.strip()
    df = df[df['product'] == 'MAGNIFICENT_MACARONS']
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    # Compute midPrice
    if 'mid_price' in df.columns:
        df['midPrice'] = df['mid_price']
    else:
        df['midPrice'] = (df['bid_price_1'] + df['ask_price_1']) / 2
    price_frames.append(df[['timestamp','midPrice']])
price_df = pd.concat(price_frames, ignore_index=True)

# 3. Merge datasets
merged = pd.merge(obs_df[['timestamp','sunlightIndex']], price_df, on='timestamp', how='inner')

# 4. Search for CSI: threshold maximizing price increase below threshold
sun_vals = np.percentile(merged['sunlightIndex'], np.linspace(1, 99, 99))
best_diff, best_t = -np.inf, None

for t in sun_vals:
    below = merged[merged['sunlightIndex'] < t]['midPrice']
    above = merged[merged['sunlightIndex'] >= t]['midPrice']
    if len(below) < 5 or len(above) < 5:
        continue
    diff = below.mean() - above.mean()
    if diff > best_diff:
        best_diff, best_t = diff, t

print(f"CSI (maximizing mean price increase below threshold): {best_t:.2f}")
print(f"Mean midPrice below CSI: {merged[merged['sunlightIndex'] < best_t]['midPrice'].mean():.2f}")
print(f"Mean midPrice above CSI: {merged[merged['sunlightIndex'] >= best_t]['midPrice'].mean():.2f}")
print(f"Difference: {best_diff:.2f}")
