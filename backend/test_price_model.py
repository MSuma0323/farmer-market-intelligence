import unittest

import pandas as pd

from backend.price_model import PriceForecaster


class PriceForecasterTest(unittest.TestCase):
    def setUp(self):
        self.model = PriceForecaster()
        rows = [
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2450, "price_lag_1": 2400, "price_lag_2": 2380, "price_lag_7": 2420, "rolling_avg_7": 2408},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2480, "price_lag_1": 2450, "price_lag_2": 2400, "price_lag_7": 2430, "rolling_avg_7": 2424},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2490, "price_lag_1": 2480, "price_lag_2": 2450, "price_lag_7": 2440, "rolling_avg_7": 2446},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2515, "price_lag_1": 2490, "price_lag_2": 2480, "price_lag_7": 2450, "rolling_avg_7": 2460},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2520, "price_lag_1": 2515, "price_lag_2": 2490, "price_lag_7": 2480, "rolling_avg_7": 2479},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2540, "price_lag_1": 2520, "price_lag_2": 2515, "price_lag_7": 2490, "rolling_avg_7": 2502},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2550, "price_lag_1": 2540, "price_lag_2": 2520, "price_lag_7": 2515, "rolling_avg_7": 2520},
            {"crop_name": "Maize", "market_name": "Arasikere APMC", "price": 2570, "price_lag_1": 2550, "price_lag_2": 2540, "price_lag_7": 2520, "rolling_avg_7": 2536},
        ]
        self.model.fit(rows)

    def test_prediction_should_stay_within_reasonable_range(self):
        data = pd.DataFrame([
            {
                "crop_name": "Maize",
                "market_name": "Arasikere APMC",
                "price_lag_1": 2000,
                "price_lag_2": 1300,
                "price_lag_7": 2200,
                "rolling_avg_7": 1800,
            }
        ])

        prediction = float(self.model.predict(data)[0])
        percent_change = abs(prediction - 2000) / 2000

        self.assertLess(percent_change, 0.15)


if __name__ == "__main__":
    unittest.main()
