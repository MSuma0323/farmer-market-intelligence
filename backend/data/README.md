# Price dataset format

Place one or more CSV files in this folder to add new crops for prediction.

## Required columns

The backend reads these columns automatically:

- date: date in YYYY-MM-DD format
- crop_name: exact crop name, for example Tomato, Onion, Brinjal, Potato
- market_name: market name, for example Arasikere APMC, Hassan APMC
- price: numeric price value
- arrival_quantity: optional but recommended
- district: optional but recommended

## Example

```csv
date,crop_name,market_name,price,arrival_quantity,district
2025-01-01,Tomato,Arasikere APMC,1200,20,Hassan
2025-01-02,Tomato,Hassan APMC,1350,18,Hassan
2025-01-03,Onion,Arasikere APMC,900,25,Hassan
2025-01-04,Onion,Hassan APMC,950,22,Hassan
2025-01-05,Brinjal,Arasikere APMC,1100,15,Hassan
2025-01-06,Brinjal,Hassan APMC,1150,14,Hassan
```

## How to add a new crop dataset

1. Create a CSV file in this folder, for example: `brinjal_prices.csv`
2. Use the headers shown above.
3. Add several rows for each crop and market.
4. Run the training step from the project root:

```powershell
python backend/train_model.py
```

5. Restart the backend app if it is already running.

Tip: for better predictions, include at least 8 to 10 rows per crop/market combination.
