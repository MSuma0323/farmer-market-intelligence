from pathlib import Path
import warnings

import pandas as pd

COLUMN_ALIASES = {
    "date": "date",
    "crop_name": "crop_name",
    "crop_name_name": "crop_name",
    "crop name": "crop_name",
    "commodity": "crop_name",
    "crop": "crop_name",
    "market_name": "market_name",
    "market name": "market_name",
    "market": "market_name",
    "price": "price",
    "modal price": "price",
    "arrival_quantity": "arrival_quantity",
    "arrival qty": "arrival_quantity",
    "arrival quantity": "arrival_quantity",
    "arrivals": "arrival_quantity",
    "district": "district",
}

EXPECTED_COLUMNS = {"date", "crop_name", "market_name", "price"}


def _normalize_columns(columns):
    return [COLUMN_ALIASES.get(str(col).strip().lower(), str(col).strip().lower()) for col in columns]


def load_price_data(data_dir: Path) -> pd.DataFrame:
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip')
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            continue
        if df.empty:
            continue

        df.columns = _normalize_columns(df.columns)
        if not EXPECTED_COLUMNS.issubset(set(df.columns)):
            continue

        for optional_col in ["arrival_quantity", "district"]:
            if optional_col not in df.columns:
                df[optional_col] = pd.NA

        df = df[["date", "crop_name", "market_name", "price", "arrival_quantity", "district"]]
        frames.append(df)

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        raise ValueError(f"No valid price data files were found in {data_dir}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        combined = pd.concat(frames, ignore_index=True)

    combined["date"] = pd.to_datetime(
        combined["date"],
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )
    combined["price"] = pd.to_numeric(combined["price"], errors="coerce")
    combined = combined.drop_duplicates(
        subset=["date", "crop_name", "market_name"], keep="last"
    )
    combined = combined.dropna(subset=["date", "crop_name", "market_name", "price"])
    combined = combined.sort_values(["crop_name", "market_name", "date"])
    combined = combined.reset_index(drop=True)

    return combined
