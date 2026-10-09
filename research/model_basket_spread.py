import pandas as pd
import matplotlib.pyplot as plt
import glob
import numpy as np

# ================= Helper Functions ===================

def load_csv_files(pattern):
    """
    Loads all CSV files matching the file pattern.
    Assumes semicolon-delimited CSV with these columns:
    day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;
    bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;
    ask_price_3;ask_volume_3;mid_price;profit_and_loss
    """
    files = glob.glob(pattern)
    dfs = []
    for file in files:
        # Read CSV using the semicolon delimiter.
        df = pd.read_csv(file, delimiter=';')
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def compute_synthetic(df, constituents):
    """
    Given a DataFrame with one row per timestamp and a basket definition (a dictionary
    mapping commodity to quantity), compute the synthetic basket price for each row.
    If a constituent is missing, its price is treated as 0.
    """
    synthetic = pd.Series(0, index=df.index, dtype=float)
    for commodity, qty in constituents.items():
        if commodity in df.columns:
            synthetic += qty * df[commodity].fillna(0)
    return synthetic

# ================= Load Prices Data ===================

# Use the prices CSV files. (The CSVs should use only the allowed columns.)
prices_file_pattern = "data/round2/prices_round_2_day_*.csv"
prices_df = load_csv_files(prices_file_pattern)

# Convert column names to uppercase for consistency.
prices_df.columns = [col.upper() for col in prices_df.columns]

# Pivot the prices data so that each row corresponds to a specific (DAY, TIMESTAMP)
# and each product becomes its own column with its MID_PRICE.
prices_pivot_ts = prices_df.pivot_table(
    index=['DAY', 'TIMESTAMP'],
    columns='PRODUCT',
    values='MID_PRICE',
    aggfunc='mean'
).reset_index()

# ================= Define Basket Constituents ===================

# Define the basket constituents (the commodity names here should match names in the data).
basket1_constituents = {'CROISSANTS': 6, 'JAMS': 3, 'DJEMBES': 1}
basket2_constituents = {'CROISSANTS': 4, 'JAMS': 2}

# ================= Compute Spread and Plot ===================

# Get the unique days from the pivoted data
days = sorted(prices_pivot_ts['DAY'].unique())

# Create subplots for Basket 1 and Basket 2 spread plots.
fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=False)

# Define x-axis ticks: from 0 to 1,000,000 in steps of 100,000.
tick_values = np.arange(0, 1000000 + 1, 100000)
tick_labels = [f"{val/1e6:.1f}M" for val in tick_values]

# ----- Basket 1 Spread -----
ax = axes[0]
for day in days:
    df_day = prices_pivot_ts[prices_pivot_ts['DAY'] == day].sort_values(by='TIMESTAMP')
    
    # Use market basket price from PICNIC_BASKET1 if present.
    if "PICNIC_BASKET1" in df_day.columns:
        market_price = df_day["PICNIC_BASKET1"]
    else:
        continue  # Skip this day if PICNIC_BASKET1 is missing.
    
    synthetic_price = compute_synthetic(df_day, basket1_constituents)
    spread = market_price - synthetic_price  # Compute spread: Market - Synthetic
    
    ax.plot(df_day['TIMESTAMP'], spread, label=f"Day {day} Basket 1 Spread")
    
ax.set_title("Basket 1: Spread (Market - Synthetic)")
ax.set_xlabel("Timestamp")
ax.set_ylabel("Spread")
ax.set_xlim(0, 1000000)
ax.set_xticks(tick_values)
ax.set_xticklabels(tick_labels)
ax.legend(fontsize='small')
ax.grid(True)

# ----- Basket 2 Spread -----
ax = axes[1]
for day in days:
    df_day = prices_pivot_ts[prices_pivot_ts['DAY'] == day].sort_values(by='TIMESTAMP')
    
    if "PICNIC_BASKET2" in df_day.columns:
        market_price = df_day["PICNIC_BASKET2"]
    else:
        continue
    
    synthetic_price = compute_synthetic(df_day, basket2_constituents)
    spread = market_price - synthetic_price
    
    ax.plot(df_day['TIMESTAMP'], spread, label=f"Day {day} Basket 2 Spread")
    
ax.set_title("Basket 2: Spread (Market - Synthetic)")
ax.set_xlabel("Timestamp")
ax.set_ylabel("Spread")
ax.set_xlim(0, 1000000)
ax.set_xticks(tick_values)
ax.set_xticklabels(tick_labels)
ax.legend(fontsize='small')
ax.grid(True)

plt.tight_layout()
plt.show()
