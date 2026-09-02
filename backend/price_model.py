class PriceForecaster:
    def __init__(self):
        self.global_mean = 0.0
        self.crop_means = {}
        self.market_means = {}

    def fit(self, rows):
        prices = [float(row["price"]) for row in rows]
        self.global_mean = sum(prices) / len(prices)

        grouped = {}
        for row in rows:
            crop = row["crop_name"]
            market = row["market_name"]
            grouped.setdefault(("crop", crop), []).append(float(row["price"]))
            grouped.setdefault(("market", crop, market), []).append(float(row["price"]))

        self.crop_means = {
            key[1]: sum(values) / len(values)
            for key, values in grouped.items()
            if key[0] == "crop"
        }
        self.market_means = {
            (key[1], key[2]): sum(values) / len(values)
            for key, values in grouped.items()
            if key[0] == "market"
        }

    def _predict_one(self, row):
        crop = row["crop_name"]
        market = row["market_name"]

        price_lag_1 = float(row["price_lag_1"])
        price_lag_2 = float(row["price_lag_2"])
        price_lag_7 = float(row["price_lag_7"])
        rolling_avg_7 = float(row["rolling_avg_7"])

        # Older saved models used ``vegetable_means``.  Keep those model files
        # usable after the field was renamed to ``crop_means``.
        crop_means = getattr(self, "crop_means", getattr(self, "vegetable_means", {}))
        market_means = getattr(self, "market_means", {})
        market_anchor = market_means.get(
            (crop, market),
            crop_means.get(crop, self.global_mean),
        )

        one_day_trend = price_lag_1 - price_lag_2
        weekly_trend = (price_lag_1 - price_lag_7) / 6
        momentum = (0.70 * one_day_trend) + (0.30 * weekly_trend)
        mean_reversion = 0.20 * (rolling_avg_7 - price_lag_1)
        market_pull = 0.04 * (market_anchor - price_lag_1)

        prediction = price_lag_1 + (0.65 * momentum) + mean_reversion + market_pull

        lower_limit = max(50, price_lag_1 * 0.65)
        upper_limit = price_lag_1 * 1.35

        return min(max(prediction, lower_limit), upper_limit)

    def predict(self, data):
        records = data.to_dict("records")
        return [self._predict_one(row) for row in records]
