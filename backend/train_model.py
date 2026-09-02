import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from data_utils import load_price_data
from price_model import PriceForecaster


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_PATH = BASE_DIR / "models" / "crop_price_model.pkl"


df = load_price_data(DATA_DIR)

df["day"] = df["date"].dt.day
df["month"] = df["date"].dt.month
df["day_of_week"] = df["date"].dt.dayofweek

groups = ["crop_name", "market_name"]
df["price_lag_1"] = df.groupby(groups)["price"].shift(1)
df["price_lag_2"] = df.groupby(groups)["price"].shift(2)
df["price_lag_7"] = df.groupby(groups)["price"].shift(7)
df["rolling_avg_7"] = df.groupby(groups)["price"].transform(
    lambda values: values.shift(1).rolling(7).mean()
)

df = df.dropna()

if len(df) < 10:
    raise ValueError("Not enough cleaned data to train the model. Add at least 10 usable rows.")

split_index = int(len(df) * 0.8)
train_df = df.iloc[:split_index]
test_df = df.iloc[split_index:]

model = PriceForecaster()
model.fit(train_df.to_dict("records"))

y_test = test_df["price"].to_numpy()
y_pred = np.array(model.predict(test_df))

mae = np.mean(np.abs(y_test - y_pred))
rmse = np.sqrt(np.mean((y_test - y_pred) ** 2))
ss_res = np.sum((y_test - y_pred) ** 2)
ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
with MODEL_PATH.open("wb") as file:
    pickle.dump(model, file)

print("Model Accuracy Results")
print("MAE:", round(float(mae), 2))
print("RMSE:", round(float(rmse), 2))
print("R2 Score:", round(float(r2), 4))
print("Training rows:", len(train_df))
print("Testing rows:", len(test_df))
print("Model saved successfully.")
