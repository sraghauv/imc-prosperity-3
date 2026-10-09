import os
import subprocess
import itertools
import json
import io
import pandas as pd

# File names
TEMPLATE_FILE = 'rahul_trader.py'
TEMP_FILE = 'temp_trader.py'

# Define grid search parameter values
fair_value_list = [10000]
take_width_list = [0.5, 1.0, 1.5]
clear_width_list = [0, 1]
default_edge_list = [1, 2, 3]


results = []

def extract_pnl(log_text):
    """
    Extract final pnl value from the backtest log text.
    The Backtester writes an "Activities log:" section with CSV data that
    includes the column "profit_and_loss". We take the last row's value.
    """
    try:
        # Split out the activities log section
        sections = log_text.split("Activities log:")
        if len(sections) < 2:
            print("Activities log section not found in log file.")
            return None
        csv_section = sections[1].split("Trade History:")[0].strip()
        
        # Read the CSV data from the string
        df = pd.read_csv(io.StringIO(csv_section), sep=";")
        final_pnl = float(df["profit_and_loss"].iloc[-1])
        return final_pnl
    except Exception as e:
        print(f"Error extracting pnl: {e}")
        return None

# Iterate over all combinations of parameter values
for fv, tw, cw, de in itertools.product(fair_value_list, take_width_list, clear_width_list, default_edge_list):
    # Read the template trader file
    with open(TEMPLATE_FILE, 'r') as f:
        content = f.read()
        
    # Replace placeholder tokens with the current combination of parameters
    content = content.replace("{FAIR_VALUE}", str(fv))
    content = content.replace("{TAKE_WIDTH}", str(tw))
    content = content.replace("{CLEAR_WIDTH}", str(cw))
    content = content.replace("{DEFAULT_EDGE}", str(de))
    
    # Write the modified algorithm to a temporary file
    with open(TEMP_FILE, 'w') as f:
        f.write(content)
    
    # Define the output log file name
    log_file = f"results_fv{fv}_tw{tw}_cw{cw}_de{de}.log"
    
    # Construct the command for the backtester
    # Here "1" represents the round number (modify as needed)
    cmd = ["prosperity3bt", TEMP_FILE, "1", "--out", log_file]
    print("Running:", " ".join(cmd))
    
    # Run the backtester command (ensure your environment is set up correctly)
    subprocess.run(cmd, check=True)
    
    # Read the backtester log file
    with open(log_file, 'r') as f:
        log_content = f.read()
    
    # Extract the PnL value from the log file
    pnl_value = extract_pnl(log_content)
    
    # Save the results for this parameter combination
    results.append({
        "fair_value": fv,
        "take_width": tw,
        "clear_width": cw,
        "default_edge": de,
        "pnl": pnl_value,
        "log": log_content
    })

# Write all results to a JSON file for later analysis
with open("grid_search_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Determine which parameter set yielded the highest PnL
best_result = max(results, key=lambda r: r["pnl"] if r["pnl"] is not None else float('-inf'))
print("Grid search complete. Summary saved to grid_search_results.json")
print("Best parameter combination:")
print(json.dumps(best_result, indent=2))
