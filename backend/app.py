import pickle
import sys
import json
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field
import pandas as pd
from . import price_model as _price_model
from .data_utils import load_price_data
from .price_model import PriceForecaster
from dotenv import load_dotenv

load_dotenv()

graphhopper_key = os.getenv("GRAPHHOPPER_API_KEY")

print("GraphHopper key loaded:", graphhopper_key is not None)

sys.modules["price_model"] = _price_model

app = FastAPI()
FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
FRONTEND_ASSETS = Path(__file__).resolve().parent.parent / "frontend" / "assets"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "vegetable_price_model.pkl"
DATA_DIR = Path(__file__).resolve().parent / "data"
FRONTEND_ASSETS.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")

with MODEL_PATH.open("rb") as file:
    model: PriceForecaster = pickle.load(file)

price_data = load_price_data(DATA_DIR)


class PriceInput(BaseModel):
    crop_name: str
    market_name: str
    day: int
    month: int
    day_of_week: int
    price_lag_1: float
    price_lag_2: float
    price_lag_7: float
    rolling_avg_7: float


class AutoPredictionInput(BaseModel):
    crop_name: str
    market_name: str | None = None
    days_ahead: int = 1


class PriceAlertInput(BaseModel):
    crop_name: str
    market_name: str
    threshold: float = Field(gt=0)
    condition: str


# Destination coordinates for the APMC market towns.  Distances are calculated
# by a driving router (rather than a straight-line estimate) from the farmer's
# GPS location to these destinations.
MARKET_COORDINATES = {
    "Arakalgud APMC": (12.7650, 76.0560),
    "Arasikere APMC": (13.3105, 76.2537),
    "Belur APMC": (13.1629, 75.8650),
    "C.R. Patna APMC": (12.9050, 76.3900),
    "Channarayapatna APMC": (12.9050, 76.3900),
    "Hassan APMC": (12.9951, 76.0882),
    "Holenarsipura APMC": (12.7863, 76.2433),
    "Sakaleshpura APMC": (12.9410, 75.7850),
}

# A conservative local hauling estimate used when the farmer has not supplied
# a carrier quote.  It is deliberately high enough that a small price premium
# does not recommend a much farther market.
DEFAULT_TRANSPORT_COST_PER_KM_QUINTAL = 12.0
MAX_RECOMMENDED_MARKET_DISTANCE_KM = 60.0


class NearbyMarketInput(AutoPredictionInput):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_accuracy_m: float | None = None
    quantity_quintals: float = Field(default=1, gt=0)
    production_cost_per_quintal: float = Field(default=0, ge=0)
    transport_cost_per_km_quintal: float = Field(
        default=DEFAULT_TRANSPORT_COST_PER_KM_QUINTAL, ge=0
    )


def get_graphhopper_key():
    """Read the key from the current process or Windows' saved user settings."""
    graphhopper_key = os.getenv("GRAPHHOPPER_API_KEY")
    if graphhopper_key:
        return graphhopper_key

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as environment_key:
            graphhopper_key, _ = winreg.QueryValueEx(
                environment_key, "GRAPHHOPPER_API_KEY"
            )
            return graphhopper_key
    except (ImportError, FileNotFoundError, OSError):
        return None


def _graphhopper_distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
    graphhopper_key = get_graphhopper_key()
    if not graphhopper_key:
        return None

    route_url = "https://graphhopper.com/api/1/route?" + urlencode([
        ("point", f"{latitude_1},{longitude_1}"),
        ("point", f"{latitude_2},{longitude_2}"),
        ("vehicle", "car"),
        ("calc_points", "false"),
        ("key", graphhopper_key),
    ])
    try:
        with urlopen(route_url, timeout=4) as response:
            route_data = json.load(response)
        distance_meters = route_data["paths"][0]["distance"]
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return None

    return round(float(distance_meters) / 1000, 1)


def _osrm_distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
    # OSRM's driving profile follows roads usable by cars and buses.
    route_url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{longitude_1},{latitude_1};{longitude_2},{latitude_2}?overview=false"
    )
    try:
        with urlopen(route_url, timeout=4) as response:
            route_data = json.load(response)
        if route_data.get("code") != "Ok":
            return None
        distance_meters = route_data["routes"][0]["distance"]
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return None

    return round(float(distance_meters) / 1000, 1)


def road_distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
    graphhopper_distance = _graphhopper_distance_km(
        latitude_1, longitude_1, latitude_2, longitude_2
    )
    if graphhopper_distance is not None:
        return graphhopper_distance, "GraphHopper driving route"

    osrm_distance = _osrm_distance_km(latitude_1, longitude_1, latitude_2, longitude_2)
    if osrm_distance is not None:
        return osrm_distance, "OSRM driving route"

    return None, None


def build_market_features(crop_name: str, market_name: str, days_ahead: int):
    if days_ahead < 1 or days_ahead > 30:
        raise HTTPException(
            status_code=500,
            detail="Forecast days must be between 1 and 30.",
        )

    system_today = pd.Timestamp.now().normalize()
    market_data = price_data[
        (price_data["crop_name"] == crop_name)
        & (price_data["market_name"] == market_name)
        & (price_data["date"] <= system_today)
    ].sort_values("date")

    if len(market_data) < 8:
        raise HTTPException(
            status_code=500,
            detail=f"Need at least 8 price records for {crop_name} in {market_name}.",
        )

    latest_date = system_today
    prices = market_data["price"].tolist()
    latest_actual_price = float(prices[-1])

    features = None
    predicted_price = None
    forecast_series = []

    for step in range(1, days_ahead + 1):
        prediction_date = latest_date + pd.Timedelta(days=step)
        features = {
            "crop_name": crop_name,
            "market_name": market_name,
            "day": int(prediction_date.day),
            "month": int(prediction_date.month),
            "day_of_week": int(prediction_date.dayofweek),
            "price_lag_1": float(prices[-1]),
            "price_lag_2": float(prices[-2]),
            "price_lag_7": float(prices[-7]),
            "rolling_avg_7": float(sum(prices[-7:]) / 7),
        }
        predicted_price = predict_from_features(features)
        prices.append(predicted_price)
        forecast_series.append({
            "day": step,
            "date": prediction_date.strftime("%Y-%m-%d"),
            "predicted_price": predicted_price,
        })

    features["forecast_days"] = days_ahead
    features["predicted_price"] = predicted_price
    features["forecast_series"] = forecast_series
    features["latest_actual_price"] = latest_actual_price
    features["today_date"] = system_today.strftime("%Y-%m-%d")
    features["prediction_date"] = prediction_date.strftime("%Y-%m-%d")

    return features


def predict_from_features(features):
    input_df = pd.DataFrame([features])
    return round(float(model.predict(input_df)[0]), 2)


@app.post("/price-alert")
@app.post("/price-alert/")
def price_alert(data: PriceAlertInput):
    if data.condition not in {"above", "below"}:
        raise HTTPException(status_code=400, detail="Condition must be above or below.")

    system_today = pd.Timestamp.now().normalize()
    market_data = price_data[
        (price_data["crop_name"] == data.crop_name)
        & (price_data["market_name"] == data.market_name)
        & (price_data["date"] <= system_today)
    ].sort_values("date")
    if market_data.empty:
        raise HTTPException(status_code=404, detail="No current price data found for this crop and market.")

    latest = market_data.iloc[-1]
    current_price = round(float(latest["price"]), 2)
    threshold_reached = (
        current_price >= data.threshold
        if data.condition == "above"
        else current_price <= data.threshold
    )
    condition_text = "at or above" if data.condition == "above" else "at or below"

    return {
        "crop_name": data.crop_name,
        "market_name": data.market_name,
        "current_price": current_price,
        "price_date": latest["date"].strftime("%Y-%m-%d"),
        "threshold": round(data.threshold, 2),
        "condition": data.condition,
        "threshold_reached": threshold_reached,
        "message": (
            f"Alert: {data.crop_name} at {data.market_name} is Rs. {current_price:,.2f} per quintal, "
            f"{condition_text} Rs. {data.threshold:,.2f}."
            if threshold_reached
            else f"No alert: the current price is Rs. {current_price:,.2f} per quintal; "
            f"the alert will trigger when it is {condition_text} Rs. {data.threshold:,.2f}."
        ),
    }


@app.get("/")
def home():
    # The UI is a single HTML file. Prevent an old cached copy from hiding
    # interface updates while the API itself is already running the new code.
    return FileResponse(FRONTEND_INDEX, headers={"Cache-Control": "no-store"})


@app.get("/favicon.ico")
def favicon():
    return FileResponse(FRONTEND_ASSETS / "farmerA.jpeg")


@app.get("/app")
def frontend_app():
    return FileResponse(FRONTEND_INDEX, headers={"Cache-Control": "no-store"})


@app.get("/metadata")
def metadata():
    crops = sorted(price_data["crop_name"].dropna().unique().tolist())
    all_markets = sorted(price_data["market_name"].dropna().unique().tolist())
    market_map = {
        crop: sorted(
            price_data[price_data["crop_name"] == crop]["market_name"].dropna().unique().tolist()
        )
        for crop in crops
    }
    market_notes = {}
    for crop in crops:
        crop_counts = (
            price_data[price_data["crop_name"] == crop]
            .groupby("market_name")
            .size()
            .to_dict()
        )
        notes = []
        for market in all_markets:
            record_count = crop_counts.get(market, 0)
            if record_count == 0:
                notes.append(f"{market}: no historical price data for {crop}.")
            elif record_count < 8:
                notes.append(f"{market}: only {record_count} price records; at least 8 are required.")
        market_notes[crop] = notes
    return {
        "crops": crops,
        "market_map": market_map,
        "market_notes": market_notes,
        "today_date": pd.Timestamp.now().normalize().strftime("%Y-%m-%d"),
        "unit": "Rs./Quintal",
    }


@app.post("/predict-price")
@app.post("/predict-price/")
def predict_price(data: PriceInput):
    input_df = pd.DataFrame([data.dict()])
    predicted_price = model.predict(input_df)[0]

    return {
        "crop_name": data.crop_name,
        "market_name": data.market_name,
        "predicted_price": round(float(predicted_price), 2),
    }


@app.post("/predict-from-dataset")
@app.post("/predict-from-dataset/")
def predict_from_dataset(data: AutoPredictionInput):
    markets = price_data[price_data["crop_name"] == data.crop_name]["market_name"].unique()

    if len(markets) == 0:
        raise HTTPException(status_code=500, detail="Crop not found in dataset.")

    selected_market = data.market_name or markets[0]

    if selected_market not in markets:
        raise HTTPException(status_code=500, detail="Market not found for selected crop.")

    features = build_market_features(data.crop_name, selected_market, data.days_ahead)

    return {
        "crop_name": data.crop_name,
        "market_name": selected_market,
        "predicted_price": features["predicted_price"],
        "forecast_days": data.days_ahead,
        "today_date": features["today_date"],
        "prediction_date": features["prediction_date"],
        "prediction_type": "recursive_multi_day",
        "features_used": features,
    }


@app.post("/best-market")
@app.post("/best-market/")
def best_market(items: list[PriceInput]):
    results = []

    for item in items:
        input_df = pd.DataFrame([item.dict()])
        predicted_price = model.predict(input_df)[0]

        results.append({
            "market_name": item.market_name,
            "predicted_price": round(float(predicted_price), 2)
        })

    best = max(results, key=lambda x: x["predicted_price"])

    return {
        "best_market": best["market_name"],
        "best_price": best["predicted_price"],
        "all_predictions": results
    }


@app.post("/best-market-from-dataset")
@app.post("/best-market-from-dataset/")
def best_market_from_dataset(data: AutoPredictionInput):
    markets = price_data[price_data["crop_name"] == data.crop_name]["market_name"].unique()

    if len(markets) == 0:
        raise HTTPException(status_code=500, detail="Crop not found in dataset.")

    results = []
    skipped_markets = []

    for market in markets:
        try:
            features = build_market_features(data.crop_name, market, data.days_ahead)
        except HTTPException as error:
            skipped_markets.append({
                "market_name": market,
                "reason": error.detail,
            })
            continue

        results.append({
            "market_name": market,
            "predicted_price": features["predicted_price"],
            "last_price": features["latest_actual_price"],
            "rolling_avg_7": round(features["rolling_avg_7"], 2),
        })

    if not results:
        raise HTTPException(
            status_code=500,
            detail="No market has enough price history. Each market needs at least 8 records.",
        )

    results = sorted(results, key=lambda x: x["predicted_price"], reverse=True)
    best = results[0]
    second_best = results[1] if len(results) > 1 else None
    price_advantage = (
        round(best["predicted_price"] - second_best["predicted_price"], 2)
        if second_best
        else 0
    )

    return {
        "crop_name": data.crop_name,
        "best_market": best["market_name"],
        "best_price": best["predicted_price"],
        "second_best_market": second_best["market_name"] if second_best else None,
        "price_advantage": price_advantage,
        "forecast_days": data.days_ahead,
        "prediction_type": "recursive_multi_day",
        "all_predictions": results,
        "skipped_markets": skipped_markets,
    }


@app.post("/nearest-market-with-best-price")
@app.post("/nearest-market-with-best-price/")
def nearest_market_with_best_price(data: NearbyMarketInput):
    print("USER LOCATION:", data.latitude, data.longitude)
    markets = price_data[price_data["crop_name"] == data.crop_name]["market_name"].unique()
    def calculate_market(market):
        coordinates = MARKET_COORDINATES.get(market)
        print("MARKET:", market, "COORDINATES:", coordinates)
        if not coordinates:
            return None
        try:
            features = build_market_features(data.crop_name, market, data.days_ahead)
        except HTTPException:
            return None

        distance_km, distance_source = road_distance_km(
            data.latitude, data.longitude, coordinates[0], coordinates[1]
        )
        if distance_km is None:
            return None
        print("VEHICLE DISTANCE:", market, distance_km, "SOURCE:", distance_source)
        quantity = data.quantity_quintals
        predicted_price = features["predicted_price"]
        revenue = round(predicted_price * quantity, 2)
        production_cost = round(data.production_cost_per_quintal * quantity, 2)
        transport_cost = round(
            distance_km * data.transport_cost_per_km_quintal * quantity, 2
        )
        transport_cost_per_quintal = round(
            distance_km * data.transport_cost_per_km_quintal, 2
        )
        net_return_per_quintal = round(
            predicted_price - transport_cost_per_quintal, 2
        )
        return {
            "market_name": market,
            "predicted_price": predicted_price,
            "distance_km": round(distance_km, 1),
            "revenue": revenue,
            "production_cost": production_cost,
            "transport_cost": transport_cost,
            "transport_cost_per_quintal": transport_cost_per_quintal,
            "net_return_per_quintal": net_return_per_quintal,
            "estimated_profit": round(revenue - production_cost - transport_cost, 2),
            "distance_source": distance_source,
        }

    # Routing calls are independent, so do them concurrently instead of making
    # the user wait for one network request to finish before starting the next.
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = [result for result in executor.map(calculate_market, markets) if result]

    filtered_results = [
        item for item in results
        if item["distance_km"] <= MAX_RECOMMENDED_MARKET_DISTANCE_KM
    ]

    distance_sources = {result["distance_source"] for result in filtered_results}

    if not filtered_results:
        raise HTTPException(
            status_code=500,
            detail="There is no nearest market for this location. Please choose a farm location closer to the market area or try a different crop.",
        )

    nearby_markets = sorted(filtered_results, key=lambda item: item["distance_km"])[:3]
    # Production cost is the same for every market; rank using the amount the
    # farmer receives per quintal after the road-transport cost.
    market_rankings = sorted(
        filtered_results, key=lambda item: item["net_return_per_quintal"], reverse=True
    )
    nearest_market = nearby_markets[0]
    best_market_after_transport = market_rankings[0]
    best_price_market = max(filtered_results, key=lambda item: item["predicted_price"])

    return {
        "nearest_market": nearest_market,
        "best_price_market": best_price_market,
        # Kept for existing clients; this is the market with the highest net
        # return, not necessarily the geographically nearest market.
        "best_nearby_market": best_market_after_transport,
        "best_market_after_transport": best_market_after_transport,
        "nearby_markets": nearby_markets,
        "market_rankings": market_rankings,
        "forecast_days": data.days_ahead,
        "location_accuracy_m": data.location_accuracy_m,
        "quantity_quintals": data.quantity_quintals,
        "production_cost_per_quintal": data.production_cost_per_quintal,
        "transport_cost_per_km_quintal": data.transport_cost_per_km_quintal,
        "distance_note": "; ".join(sorted(distance_sources)),
        "max_recommended_distance_km": MAX_RECOMMENDED_MARKET_DISTANCE_KM,
    }
