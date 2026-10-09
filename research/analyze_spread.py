import sys
import pandas as pd
import matplotlib.pyplot as plt

def main():
    """
    Usage (from the command line):
      python baskets.py input_data.csv output_baskets.csv

    - input_data.csv is your CSV with semicolon delimiters (e.g. day;timestamp;product;...).
    - output_baskets.csv will contain the computed basket prices and spread statistics for
      PICNIC_BASKET1 and PICNIC_BASKET2.
    """
    if len(sys.argv) < 3:
        print("Usage: python baskets.py input_data.csv output_baskets.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # 1. Read the CSV file with semicolon as a delimiter.
    df = pd.read_csv(input_file, sep=';')

    # Ensure mid_price is numeric.
    df["mid_price"] = pd.to_numeric(df["mid_price"], errors='coerce')

    # 2. Filter the underlying products and basket products.
    # Underlying products for synthetic calculations: CROISSANTS, JAMS, DJEMBES
    df_underlying = df[df["product"].isin(["CROISSANTS", "JAMS", "DJEMBES"])]
    
    # Basket rows (for actual reported basket prices)
    df_basket1 = df[df["product"] == "PICNIC_BASKET1"]
    df_basket2 = df[df["product"] == "PICNIC_BASKET2"]

    # 3. Pivot the underlying data so each product becomes a column (indexed by timestamp)
    underlying = df_underlying.pivot(index="timestamp", columns="product", values="mid_price")
    
    # 4. Extract basket actual prices (set timestamp as index)
    basket1_actual = df_basket1.set_index("timestamp")["mid_price"]
    basket2_actual = df_basket2.set_index("timestamp")["mid_price"]

    # 5. Compute synthetic basket prices:
    # PICNIC_BASKET1: 6 * CROISSANTS + 3 * JAMS + 1 * DJEMBES
    synthetic_basket1 = 6 * underlying["CROISSANTS"] + 3 * underlying["JAMS"] + underlying["DJEMBES"]
    # PICNIC_BASKET2: 4 * CROISSANTS + 2 * JAMS
    synthetic_basket2 = 4 * underlying["CROISSANTS"] + 2 * underlying["JAMS"]

    # 6. Create DataFrames that combine actual and synthetic prices, and add a Basket identifier.
    basket1_df = pd.DataFrame({
        "timestamp": basket1_actual.index,
        "Actual": basket1_actual.values,
        "Synthetic": synthetic_basket1.loc[basket1_actual.index].values
    })
    basket1_df["Basket"] = "PICNIC_BASKET1"
    # Calculate the spread for PICNIC_BASKET1 (Actual - Synthetic)
    basket1_df["Spread"] = basket1_df["Actual"] - basket1_df["Synthetic"]
    
    basket2_df = pd.DataFrame({
        "timestamp": basket2_actual.index,
        "Actual": basket2_actual.values,
        "Synthetic": synthetic_basket2.loc[basket2_actual.index].values
    })
    basket2_df["Basket"] = "PICNIC_BASKET2"
    # Calculate the spread for PICNIC_BASKET2 (Actual - Synthetic)
    basket2_df["Spread"] = basket2_df["Actual"] - basket2_df["Synthetic"]

    # 7. Compute statistics (mean and std) for the spreads.
    mean_spread_basket1 = basket1_df["Spread"].mean()
    std_spread_basket1 = basket1_df["Spread"].std()
    mean_spread_basket2 = basket2_df["Spread"].mean()
    std_spread_basket2 = basket2_df["Spread"].std()

    print("Statistics for PICNIC_BASKET1 Spread:")
    print(f"  Mean: {mean_spread_basket1:.2f}, Std: {std_spread_basket1:.2f}")
    print("Statistics for PICNIC_BASKET2 Spread:")
    print(f"  Mean: {mean_spread_basket2:.2f}, Std: {std_spread_basket2:.2f}")

    # 8. Combine both basket DataFrames.
    combined_df = pd.concat([basket1_df, basket2_df], ignore_index=True)
    
    # 9. Write the combined basket data (including spread statistics) to output CSV (semicolon as delimiter).
    combined_df.to_csv(output_file, index=False, sep=';')
    print(f"Basket prices and spread data written to {output_file}")

    # 10. Visualize the spread between actual and synthetic prices.
    # Create separate plots (one for each basket) for the spread.
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(10, 8), sharex=True)

    # Plot spread for PICNIC_BASKET1:
    basket1_df_sorted = basket1_df.sort_values("timestamp")
    axes[0].plot(basket1_df_sorted["timestamp"], basket1_df_sorted["Spread"],
                 linestyle='-', linewidth=0.5, label='Spread (Actual - Synthetic)')
    axes[0].set_title("PICNIC_BASKET1: Spread (Actual - Synthetic) Over Time")
    axes[0].set_ylabel("Spread")
    axes[0].legend()
    axes[0].grid(True)

    # Plot spread for PICNIC_BASKET2:
    basket2_df_sorted = basket2_df.sort_values("timestamp")
    axes[1].plot(basket2_df_sorted["timestamp"], basket2_df_sorted["Spread"],
                 linestyle='-', linewidth=0.5, label='Spread (Actual - Synthetic)')
    axes[1].set_title("PICNIC_BASKET2: Spread (Actual - Synthetic) Over Time")
    axes[1].set_xlabel("Timestamp")
    axes[1].set_ylabel("Spread")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
