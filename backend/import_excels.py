#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd

# heuristic column name sets we expect
DATE_KEYS = {"date", "arrival date", "day"}
MARKET_KEYS = {"market", "market name", "market_name"}
PRICE_KEYS = {"modal", "modal price", "price", "modal_price"}
ARRIVAL_KEYS = {"arrival", "arrival_quantity", "arrivals"}
DISTRICT_KEYS = {"district"}


def find_col(cols, keys):
    cols_l = {c.lower(): c for c in cols}
    for k in keys:
        for c_lower, c_orig in cols_l.items():
            if k in c_lower:
                return c_orig
    return None


def normalize_frame(df, default_veg):
    cols = df.columns.tolist()
    date_col = find_col(cols, DATE_KEYS)
    market_col = find_col(cols, MARKET_KEYS)
    price_col = find_col(cols, PRICE_KEYS)
    arrival_col = find_col(cols, ARRIVAL_KEYS)
    district_col = find_col(cols, DISTRICT_KEYS)

    if price_col is None or date_col is None or market_col is None:
        return None  # can't normalize

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[date_col], errors="coerce")
    out["market_name"] = df[market_col].astype(str).str.strip()
    out["price"] = pd.to_numeric(df[price_col], errors="coerce")
    out["crop_name"] = default_cop
    if arrival_col:
        out["arrival_quantity"] = pd.to_numeric(df[arrival_col], errors="coerce")
    if district_col:
        out["district"] = df[district_col].astype(str).str.strip()
    out = out.dropna(subset=["date", "market_name", "price"])
    return out


def main(src_dir, out_dir, cop_arg):
    src = Path(src_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"Source folder not found: {src}")
        return

    for x in sorted(src.glob("*.xlsx")):
        base = x.stem
        default_cop = cop_arg or base.split("_")[0].title()
        frames = []
        try:
            xls = pd.ExcelFile(x)
            for sheet in xls.sheet_names:
                df = pd.read_excel(x, sheet_name=sheet)
                norm = normalize_frame(df, default_cop)
                if norm is not None and len(norm):
                    frames.append(norm)
        except Exception as e:
            print(f"Skipping {x.name}: read error {e}")
            continue

        if not frames:
            print(f"No usable sheets in {x.name}; skipped")
            continue

        merged = pd.concat(frames, ignore_index=True)
        merged = merged.drop_duplicates(subset=["date", "crop_name", "market_name"], keep="last")
        merged = merged.sort_values(["crop_name", "market_name", "date"])
        out_file = out / f"{base}.csv"
        merged.to_csv(out_file, index=False)
        print(f"Wrote {out_file} ({len(merged)} rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="backend/data/raw_excels", help="source folder with xlsx files")
    parser.add_argument("--out", default="backend/data", help="output folder for CSVs")
    parser.add_argument("--crop", default="", help="optional crop name (overrides inferred)")
    args = parser.parse_args()
    main(args.src, args.out, args.crop or None)
