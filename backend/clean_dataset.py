from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = Path(r"C:\Users\user\Downloads\Tomato Hassan (1).xlsx")
OUTPUT_FILE = BASE_DIR / "data" / "crop_prices.csv"


def clean_market_name(value):
    if pd.isna(value):
        return value

    name = str(value).strip()
    replacements = {
        "ARSIKERE": "Arasikere APMC",
        "HASSAN": "Hassan APMC",
        "C.R.PATNA": "C.R. Patna APMC",
        "BELUR": "Belur APMC",
        "ARAKALGUD": "Arakalgud APMC",
    }
    return replacements.get(name.upper(), name)


def clean_standard_sheet(path, sheet_name):
    df = pd.read_excel(path, sheet_name=sheet_name)

    if not {"Date", "Market", "Modal"}.issubset(df.columns):
        return pd.DataFrame()

    df["Market"] = df["Market"].ffill()
    cleaned = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Date"], errors="coerce"),
            "crop_name": "Tomato",
            "market_name": df["Market"].map(clean_market_name),
            "price": pd.to_numeric(df["Modal"], errors="coerce"),
            "arrival_quantity": pd.to_numeric(df.get("Arrivals"), errors="coerce"),
            "district": df.get("District", "Hassan"),
        }
    )

    return cleaned


def clean_sheet1(path):
    df = pd.read_excel(path, sheet_name="Sheet1")

    if not {"Date", "Market", "Modal Price"}.issubset(df.columns):
        return pd.DataFrame()

    cleaned = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Date"], errors="coerce"),
            "crop_name": "Tomato",
            "market_name": df["Market"].map(clean_market_name),
            "price": pd.to_numeric(df["Modal Price"], errors="coerce"),
            "arrival_quantity": pd.NA,
            "district": "Hassan",
        }
    )

    return cleaned


def clean_report_sheet(path):
    raw = pd.read_excel(path, sheet_name="Daily Price Arrival Report-07-1", header=None)
    header_row = raw.index[raw.apply(lambda row: row.astype(str).str.contains("Arrival Date").any(), axis=1)]

    if len(header_row) == 0:
        return pd.DataFrame()

    start = int(header_row[0])
    df = raw.iloc[start + 1 :].copy()
    df.columns = raw.iloc[start].tolist()

    if not {"Arrival Date", "Market", "Modal Price"}.issubset(df.columns):
        return pd.DataFrame()

    cleaned = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Arrival Date"], errors="coerce"),
            "crop_name": "Tomato",
            "market_name": df["Market"].map(clean_market_name),
            "price": pd.to_numeric(df["Modal Price"], errors="coerce"),
            "arrival_quantity": pd.to_numeric(df.get("Arrival Quantity"), errors="coerce"),
            "district": df.get("District", "Hassan"),
        }
    )

    return cleaned


def main():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {SOURCE_FILE}")

    excel_file = pd.ExcelFile(SOURCE_FILE)
    frames = [clean_report_sheet(SOURCE_FILE)]

    if "Sheet1" in excel_file.sheet_names:
        frames.append(clean_sheet1(SOURCE_FILE))

    for sheet_name in excel_file.sheet_names:
        if sheet_name.startswith("Sheet") and sheet_name != "Sheet1":
            frames.append(clean_standard_sheet(SOURCE_FILE, sheet_name))

    cleaned = pd.concat(frames, ignore_index=True)
    cleaned = cleaned.dropna(subset=["date", "market_name", "price"])
    cleaned = cleaned[cleaned["price"] > 0]
    cleaned["date"] = cleaned["date"].dt.date
    cleaned["market_name"] = cleaned["market_name"].astype(str).str.strip()
    cleaned["crop_name"] = cleaned["crop_name"].astype(str).str.strip()
    cleaned = cleaned.drop_duplicates(subset=["date", "crop_name", "market_name"], keep="last")
    cleaned = cleaned.sort_values(["crop_name", "market_name", "date"])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUTPUT_FILE, index=False)

    print(f"Cleaned rows: {len(cleaned)}")
    print(f"Markets: {', '.join(sorted(cleaned['market_name'].unique()))}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
