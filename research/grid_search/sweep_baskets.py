import os
import subprocess
import itertools
import json
import io
import pandas as pd

# File names (modify these as needed)
TEMPLATE_FILE = 'Nihal_Trader.py'
TEMP_FILE = 'temp_trader.py'

# Define grid search parameter values for the baskets and constituent filters.
# PICNIC_BASKET1 parameters:
basket1_zscore_list = [2.0, 2.5, 3.0]       # z-score threshold for basket spread
basket1_target_list = [40, 50, 60]            # target position for PICNIC_BASKET1
basket1_window_list = [30, 45, 60]            # rolling window for spread std dev

# PICNIC_BASKET2 parameters:
basket2_zscore_list = [2.0, 2.5, 3.0]
basket2_target_list = [20, 30, 40]
basket2_window_list = [30, 45, 60]

# Constituent filter parameters (applied identically to CROISSANTS, JAMS, and DJEMBES):
constituent_zscore_list = [0.8, 1.0, 1.2]     # z-score threshold for each commodity
constituent_window_list = [40, 50, 60]         # history window for commodity prices

results = []

def extract_pnl(log_text):
    """
    Extract the final PnL value from the backtester log text.
    The backtester prints an "Activities log:" section with CSV data including a column
    "profit_and_loss". This function takes the last row's value.
    Adjust the regex/logic if your output format is different.
    """
    try:
        # Split out the activities log section.
        sections = log_text.split("Activities log:")
        if len(sections) < 2:
            print("Activities log section not found in log file.")
            return None
        csv_section = sections[1].split("Trade History:")[0].strip()
        
        # Read the CSV data from the string.
        df = pd.read_csv(io.StringIO(csv_section), sep=";")
        final_pnl = float(df["profit_and_loss"].iloc[-1])
        return final_pnl
    except Exception as e:
        print(f"Error extracting pnl: {e}")
        return None

# Grid search over all combinations.
for (b1_z, b1_target, b1_win, b2_z, b2_target, b2_win,
     cons_z, cons_win) in itertools.product(
    basket1_zscore_list, basket1_target_list, basket1_window_list,
    basket2_zscore_list, basket2_target_list, basket2_window_list,
    constituent_zscore_list, constituent_window_list):

    # Read the trader file template.
    with open(TEMPLATE_FILE, 'r') as f:
        content = f.read()
        
    # Replace placeholder tokens with the current parameter combination.
    content = content.replace("{BASKET1_ZSCORE}", str(b1_z))
    content = content.replace("{BASKET1_TARGET}", str(b1_target))
    content = content.replace("{BASKET1_WINDOW}", str(b1_win))
    
    content = content.replace("{BASKET2_ZSCORE}", str(b2_z))
    content = content.replace("{BASKET2_TARGET}", str(b2_target))
    content = content.replace("{BASKET2_WINDOW}", str(b2_win))
    
    content = content.replace("{CONS_ZSCORE}", str(cons_z))
    content = content.replace("{CONS_WINDOW}", str(cons_win))
    
    # Write the modified trader to a temporary file.
    with open(TEMP_FILE, 'w') as f:
        f.write(content)
    
    # Define a log file name that includes the parameter values.
    log_file = f"results_b1z{b1_z}_b1t{b1_target}_b1w{b1_win}_b2z{b2_z}_b2t{b2_target}_b2w{b2_win}_consz{cons_z}_consw{cons_win}.log"
    
    # Construct the command for the backtester.
    # Here, "2" is the round number; adjust if needed.
    cmd = ["prosperity3bt", TEMP_FILE, "2", "--out", log_file]
    print("Running:", " ".join(cmd))
    
    # Run the backtester (ensure your environment is set correctly).
    subprocess.run(cmd, check=True)
    
    # Read the backtester log file.
    with open(log_file, 'r') as f:
        log_content = f.read()
    
    # Extract the PnL value.
    pnl_value = extract_pnl(log_content)
    
    # Save the parameters and corresponding profit.
    results.append({
        "basket1_zscore": b1_z,
        "basket1_target": b1_target,
        "basket1_window": b1_win,
        "basket2_zscore": b2_z,
        "basket2_target": b2_target,
        "basket2_window": b2_win,
        "constituent_zscore": cons_z,
        "constituent_window": cons_win,
        "pnl": pnl_value,
        "log": log_content
    })
    
    print(f"Params: B1 z={b1_z}, t={b1_target}, win={b1_win}; "
          f"B2 z={b2_z}, t={b2_target}, win={b2_win}; "
          f"Cons: z={cons_z}, win={cons_win} => PnL: {pnl_value}")

# Sort the results (highest profit first)
results.sort(key=lambda r: r["pnl"] if r["pnl"] is not None else float('-inf'), reverse=True)

# Save the full grid search results to a JSON file.
with open("grid_search_baskets_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Print the best parameter combination.
if results:
    best = results[0]
    print("\nBest Parameter Combination:")
    print(json.dumps(best, indent=2))

print("Grid search complete. Summary saved to grid_search_baskets_results.json")
