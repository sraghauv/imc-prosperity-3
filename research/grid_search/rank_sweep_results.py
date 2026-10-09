import re
import json

# The name of the text file that contains the grid search output.
INPUT_FILE = "output.txt"
# Profit threshold
PROFIT_THRESHOLD = 20000

def parse_block(block):
    """
    Given a block of text from the grid search output, extract:
      - The parameters used (from the "Parameters used:" line)
      - The final "Total profit:" value (taken from the profit summary)
    
    Returns a tuple (params, profit) where:
      - params is a dict mapping parameter names to their string values.
      - profit is an integer value.
    """
    # Find the parameters used line.
    # Example:
    # "Parameters used: FAIR_VALUE=10000, TAKE_WIDTH=0, CLEAR_WIDTH=0, DEFAULT_EDGE=0, SOFT_LIMIT=15"
    param_line_match = re.search(r"Parameters used:\s*(.*)", block)
    params = {}
    if param_line_match:
        param_line = param_line_match.group(1)
        for pair in param_line.split(","):
            parts = pair.strip().split("=")
            if len(parts) == 2:
                key, value = parts
                params[key.strip()] = value.strip()
    
    # Find all occurrences of "Total profit:" in the block.
    profit_matches = re.findall(r"Total profit:\s*([\d,]+)", block)
    profit = None
    if profit_matches:
        profit_str = profit_matches[-1]
        try:
            profit = int(profit_str.replace(",", ""))
        except ValueError:
            profit = None
    
    return params, profit

def main():
    with open(INPUT_FILE, "r") as f:
        content = f.read()
    
    # Split the content into blocks using a line of repeated "=" as a separator.
    blocks = re.split(r"\n={5,}\n", content)
    
    results = []
    for block in blocks:
        block = block.strip()
        if block:
            params, profit = parse_block(block)
            if params and profit is not None:
                results.append({
                    "params": params,
                    "profit": profit
                })
    
    if not results:
        print("No valid results found in the grid search output.")
        return

    # Filter to keep only those results that meet the profit threshold.
    above_threshold = [r for r in results if r["profit"] >= PROFIT_THRESHOLD]
    # Sort them in descending order based on profit.
    sorted_results = sorted(above_threshold, key=lambda r: r["profit"], reverse=True)
    
    # Determine the best result (if any exist).
    if sorted_results:
        best = sorted_results[0]
    else:
        best = None

    print("Grid Search Analysis:")
    print("---------------------")
    if best:
        print("Best parameter combination:")
        print(json.dumps(best, indent=2))
    else:
        print("No parameter combination reached the desired profit threshold.")

    print("\nTotal number of combinations with profit >= {}: {}".format(PROFIT_THRESHOLD, len(sorted_results)))
    print("\nAll combinations with profit >= {} (sorted descending):".format(PROFIT_THRESHOLD))
    for res in sorted_results:
        print(json.dumps(res, indent=2))
        print("-" * 80)

if __name__ == "__main__":
    main()
