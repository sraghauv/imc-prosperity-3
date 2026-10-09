import os
import subprocess
import itertools
import json
import io
import pandas as pd

# File names
TEMPLATE_FILE = 'rahul_trader.py'
TEMP_FILE = 'temp_trader.py'
OUTPUT_FILE = "output.txt"   # File to capture terminal output (optional)

# Define grid search parameter values
prevent_adverse_list = [True, False]
adverse_volume = [10,15,20,25,30,35,40]
reversion_beta = [.1, .15, .2, .25, .3, .35, .4]
join_edge_list = [0]
disregard_edge_list = [1]

results = []

def extract_pnl(log_text):
    """
    Extract final pnl value from the backtest log text.
    The Backtester writes an "Activities log:" section with CSV data that
    includes the column "profit_and_loss". We take the last row's value.
    """
    try:
        # Split out the activities log section; adjust if your delimiter differs.
        sections = log_text.split("Activities log:")
        if len(sections) < 2:
            return None
        csv_section = sections[1].split("Trade History:")[0].strip()
        
        # Read the CSV data from the string
        df = pd.read_csv(io.StringIO(csv_section), sep=";")
        final_pnl = float(df["profit_and_loss"].iloc[-1])
        return final_pnl
    except Exception as e:
        print(f"Error extracting pnl: {e}")
        return None

# Optional: Clear the OUTPUT_FILE at the beginning
with open(OUTPUT_FILE, "w") as out_file:
    out_file.write("Grid Search Output:\n\n")

# Iterate over all combinations of parameter values
for pa, av, rb, je, de in itertools.product(prevent_adverse_list, adverse_volume, reversion_beta, disregard_edge_list, join_edge_list):
    # Read the template trader file
    with open(TEMPLATE_FILE, 'r') as f:
        content = f.read()
        
    # Replace the placeholder tokens with the current combination of parameter values
    content = content.replace("{PREVENT_ADVERSE}", str(pa))
    content = content.replace("{ADVERSE_VOLUME}", str(av))
    content = content.replace("{REVERSION_BETA}", str(rb))
    content = content.replace("{DISREGARD_EDGE}", str(de))
    content = content.replace("{JOIN_EDGE}", str(je))  # Example for soft_position_limit
    
    # Write the modified algorithm to a temporary file
    with open(TEMP_FILE, 'w') as f:
        f.write(content)
    
    # Construct the command for the backtester
    # NOTE: We pass only "--no-out" (without an output filename)
    cmd = ["prosperity3bt", TEMP_FILE, "1", "--no-out"]
    
    # Append the command and parameters info to OUTPUT_FILE before running
    with open(OUTPUT_FILE, "a") as out_file:
         out_file.write("Running command: " + " ".join(cmd) + "\n")
         out_file.write("Parameters used: PREVENT_ADVERSE={}, ADVERSE_VOLUME={}, REVERSION_BETA={}, DISREGARD_EDGE={}, JOIN_EDGE={}\n".format(pa, av, rb, de,je))
    
    
    # Run the backtester command and capture its output
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
    # Optionally append the captured output to the OUTPUT_FILE
    with open(OUTPUT_FILE, "a") as out_file:
         out_file.write(result.stdout)
         out_file.write("\n" + "="*80 + "\n\n")
    
    # Instead of reading a generated log file, we use the output captured in 'result.stdout'
    log_content = result.stdout
    
    # Extract the final PnL value from the log content
    pnl_value = extract_pnl(log_content)
    
    # Save the results for this parameter combination
    results.append({
        "prevent_adverse": pa ,
        "adverse_volume": av,
        "reversion_beta": rb,
        "disregard_edge": de,
        "join_edge": je
    })

# Write all grid search results to a JSON file
with open("grid_search_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Determine which parameter combination yielded the highest PnL (if any PnL was extracted)
best_result = max(results, key=lambda r: r["pnl"] if r["pnl"] is not None else float('-inf'))
print("Grid search complete. Summary saved to grid_search_results.json")
print("Best parameter combination:")
print(json.dumps(best_result, indent=2))
