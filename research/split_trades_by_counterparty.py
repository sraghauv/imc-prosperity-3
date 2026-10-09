#!/usr/bin/env python3
import csv
import argparse
import os

def main():
    parser = argparse.ArgumentParser(
        description="Split trade files into per-name CSVs of transactions where they are buyer or seller"
    )
    parser.add_argument(
        "csvfiles",
        nargs="+",
        help="Paths to semicolon-delimited trade CSV(s) (with header: timestamp;buyer;seller;…)"
    )
    parser.add_argument(
        "-o", "--outdir",
        default="by_name",
        help="Output directory for per-name CSVs (default: './by_name')"
    )
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.outdir, exist_ok=True)

    # Map each name to list of rows (dicts)
    trades_by_name = {}
    fieldnames = None

    for path in args.csvfiles:
        with open(path, newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            if fieldnames is None:
                fieldnames = reader.fieldnames
            for row in reader:
                # For each unique name in buyer/seller
                for name in {row["buyer"], row["seller"]}:
                    trades_by_name.setdefault(name, []).append(row)

    # Write out per-name CSVs
    for name, rows in trades_by_name.items():
        # sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in name)
        outfile = os.path.join(args.outdir, f"{safe_name}.csv")
        with open(outfile, "w", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(trades_by_name)} files to '{args.outdir}/'")

if __name__ == "__main__":
    main()
