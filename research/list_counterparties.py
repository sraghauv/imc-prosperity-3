#!/usr/bin/env python3
import csv
import argparse

def process_file(path):
    seen = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            for name in (row["buyer"], row["seller"]):
                if name not in seen:
                    seen.append(name)

    print(f"# {path}")
    print("unique_names = [")
    for name in seen:
        print(f"    '{name}',")
    print("]\n")

def main():
    parser = argparse.ArgumentParser(
        description="Print unique buyer+seller names from one or more semicolon‑delimited CSVs"
    )
    parser.add_argument(
        "csvfiles",
        nargs="+",
        help="Path(s) to your CSV (with header: timestamp;buyer;seller;…)"
    )
    args = parser.parse_args()

    for csvfile in args.csvfiles:
        process_file(csvfile)

if __name__ == "__main__":
    main()
