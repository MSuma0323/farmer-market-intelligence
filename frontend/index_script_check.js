
    // The FastAPI server serves both this page and the prediction API.
    // Using the current origin prevents requests from being sent to a
    // different port when the server is started with its default settings.
    const API_BASE_URL = window.location.origin;

    const form = document.getElementById("predictionForm");
    const statusBox = document.getElementById("status");
    const readingSource = document.getElementById("readingSource");
    const predictedPrice = document.getElementById("predictedPrice");
    const predictionDetails = document.getElementById("predictionDetails");
    const nearestMarket = document.getElementById("nearestMarket");
    const locationUsed = document.getElementById("locationUsed");
    const nearestMarketDetails = document.getElementById("nearestMarketDetails");
    const forecastChangeDialog = document.getElementById("forecastChangeDialog");
    const forecastChangeTitle = document.getElementById("forecastChangeTitle");
    const forecastChangeAmount = document.getElementById("forecastChangeAmount");
    const forecastChangeMessage = document.getElementById("forecastChangeMessage");
    const bestMarket = document.getElementById("bestMarket");
    const bestMarketDetails = document.getElementById("bestMarketDetails");
    const marketList = document.getElementById("marketList");
    const bestMarketButton = document.getElementById("bestMarketButton");
    const nearestMarketButton = document.getElementById("nearestMarketButton");
    const farmMapButton = document.getElementById("farmMapButton");
    const farmLocationDialog = document.getElementById("farmLocationDialog");
    const farmMapSelection = document.getElementById("farmMapSelection");
    const useGpsLocationButton = document.getElementById("useGpsLocationButton");
    const farmSearchInput = document.getElementById("farmSearchInput");
    const useCurrentLocationButton = document.getElementById("useCurrentLocationButton");
    const farmSearchResults = document.getElementById("farmSearchResults");
    let selectedFarmLocation = null;
    let pendingFarmLocation = null;
    let farmMap;
    let farmMarker;
    function formatQuintalPrice(value) {
      return `â‚¹${Number(value).toFixed(2)} / quintal`;
    }

    function formatForecastSeries(series) {
      if (!Array.isArray(series) || series.length < 2) return "";
      const dailyPrices = series
        .map((item) => `Day ${item.day}: ${formatQuintalPrice(item.predicted_price)}`)
        .join(" | ");
      return ` Daily forecast: ${dailyPrices}.`;
    }

    function showForecastChange(data) {
      const latestPrice = Number(data.features_used?.latest_actual_price);
      const forecastPrice = Number(data.predicted_price);
      if (!Number.isFinite(latestPrice) || !Number.isFinite(forecastPrice)) return;

      const difference = forecastPrice - latestPrice;
      if (Math.abs(difference) < 0.01) return;

      const direction = difference > 0 ? "increase" : "decrease";
      const directionText = difference > 0 ? "increased" : "decreased";
      const percentage = Math.abs((difference / latestPrice) * 100);
      forecastChangeDialog.className = `alert-dialog forecast-change-dialog ${direction}`;
      forecastChangeTitle.textContent = `Expected price ${directionText}`;
      forecastChangeAmount.textContent = `${difference > 0 ? "+" : "-"}${formatQuintalPrice(Math.abs(difference))}`;
      forecastChangeMessage.textContent = `For ${data.crop_name} at ${data.market_name}, the forecast for ${data.forecast_days} day(s) is ${formatQuintalPrice(forecastPrice)}. The latest recorded price is ${formatQuintalPrice(latestPrice)}, a ${percentage.toFixed(1)}% ${directionText}.`;
      forecastChangeDialog.showModal();
    }

    function showReadingSource(dateValue) {
      const cropName = document.getElementById("cropName").value;
      const marketName = document.getElementById("marketName").value;
      const dateText = dateValue ? ` | Date: ${dateValue}` : "";
      readingSource.textContent = `Today reading: ${cropName} prices at ${marketName}${dateText}`;
    }

    function getInputPayload() {
      return {
        crop_name: document.getElementById("cropName").value,
        market_name: document.getElementById("marketName").value,
        days_ahead: Number(document.getElementById("daysAhead").value)
      };
    }

    function getTransportPayload(position) {
      return {
        ...getInputPayload(),
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        location_accuracy_m: position.coords.accuracy
      };
    }

    async function postJson(path, payload) {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        let message = `Request failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          message = errorData.detail || message;
        } catch (error) {
          message = message;
        }
        throw new Error(message);
      }

      return response.json();
    }

    let marketMap = {};

    function populateMarkets(crop) {
      const marketSelect = document.getElementById("marketName");
      const markets = marketMap[crop] || [];
      if (markets.length === 0) {
        marketSelect.innerHTML = '<option value="">No markets available</option>';
        return;
      }
      marketSelect.innerHTML = markets
        .map((market) => `<option value="${market}">${market}</option>`)
        .join("");
    }

    async function loadMetadata() {
      try {
        const response = await fetch(`${API_BASE_URL}/metadata`);
        const data = await response.json();
        const cropSelect = document.getElementById("cropName");

        if (data.crops && data.crops.length > 0) {
          cropSelect.innerHTML = data.crops
            .map((crop) => `<option value="${crop}">${crop}</option>`)
            .join("");
        }

        marketMap = data.market_map || {};
        if (cropSelect.options.length > 0) {
          populateMarkets(cropSelect.value);
        }
        showReadingSource(data.today_date);
      } catch (error) {
        statusBox.textContent = "Using default crop list. Restart the backend if metadata does not load.";
      }
    }

    document.getElementById("cropName").addEventListener("change", (event) => {
      populateMarkets(event.target.value);
      showReadingSource();
    });

    document.getElementById("marketName").addEventListener("change", () => showReadingSource());

    function setBusy(isBusy) {
      form.querySelectorAll("button").forEach((button) => {
        button.disabled = isBusy;
      });
    }

    function normalizePlaceText(value) {
      return String(value || "")
        .toLowerCase()
        .replace(/[()]/g, " ")
        .replace(/[^a-z0-9\s]/g, " ")
        .replace(/\b(taluk|taluka|district|village|grama|panchayat|hobli|hobali|hamlet|neighborhood)\b/gi, " ")
        .replace(/\s+/g, " ")
        .trim();
    }

    function rankSearchResult(query, result) {
      const normalizedQuery = normalizePlaceText(query);
      const displayText = [
        result.display_name,
        result.address?.village,
        result.address?.hamlet,
        result.address?.town,
        result.address?.city,
        result.name,
        result?.locality
      ].filter(Boolean).join(" ");
      const normalizedText = normalizePlaceText(displayText);
      if (!normalizedQuery) return 0;

      let score = 0;
      if (normalizedText === normalizedQuery) score += 1000;
      if (normalizedText.startsWith(normalizedQuery)) score += 250;
      if (normalizedText.includes(normalizedQuery)) score += 120;
      if (normalizedText.includes(normalizedQuery.replace(/s$/, ""))) score += 40;
      if (normalizedText.includes("hassan")) score += 20;
      if (normalizedText.includes("karnataka")) score += 15;
      if (normalizedText.includes(normalizedQuery.split(" ")[0])) score += 10;
      if (normalizedText.includes("kunchur") && !normalizedQuery.includes("kunchur")) score -= 300;
      if (normalizedText.includes("haluvagalu") && normalizedQuery.includes("haluvagalu")) score += 80;
      return score;
    }

    function getCurrentLocation() {
      if (!navigator.geolocation) {
        return Promise.reject(new Error("LOCATION_UNAVAILABLE"));
      }

      return new Promise((resolve, reject) => {
        const accuracyTargets = [25, 50, 100, 250, 500];
        let bestPosition = null;
        let attempt = 0;
        let settled = false;
        let timeoutId = null;

        function finish(position) {
          if (settled) return;
          settled = true;
          clearTimeout(timeoutId);
          resolve(position);
        }

        function finishError(error) {
          if (settled) return;
          settled = true;
          clearTimeout(timeoutId);
          reject(error);
        }

        function tryLocation() {
          if (settled) return;

          navigator.geolocation.getCurrentPosition((position) => {
            const accuracy = Number(position?.coords?.accuracy);
            const safeAccuracy = Number.isFinite(accuracy) ? accuracy : Number.MAX_SAFE_INTEGER;

            if (!bestPosition || safeAccuracy < Number(bestPosition.coords.accuracy || Number.MAX_SAFE_INTEGER)) {
              bestPosition = position;
            }

            const targetAccuracy = accuracyTargets[Math.min(attempt, accuracyTargets.length - 1)];
            if (safeAccuracy <= targetAccuracy) {
              finish(position);
              return;
            }

            if (attempt >= accuracyTargets.length - 1) {
              finish(bestPosition || position);
              return;
            }

            attempt += 1;
            setTimeout(tryLocation, 1200);
          }, (error) => {
            if (error.code === error.PERMISSION_DENIED) {
              finishError(new Error("LOCATION_PERMISSION_DENIED"));
              return;
            }
            if (bestPosition) {
              finish(bestPosition);
              return;
            }
            if (attempt >= accuracyTargets.length - 1) {
              finishError(new Error("LOCATION_UNAVAILABLE"));
              return;
            }
            attempt += 1;
            setTimeout(tryLocation, 1200);
          }, {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
          });
        }

        timeoutId = setTimeout(() => {
          if (bestPosition) finish(bestPosition);
          else finishError(new Error("LOCATION_UNAVAILABLE"));
        }, 30000);

        tryLocation();
      });
    }

    function getFarmLocation() {
      return selectedFarmLocation;
    }

    async function getPlaceName(position) {
      if (position.placeName) return position.placeName;
      const { latitude, longitude } = position.coords;
      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=18&lat=${latitude}&lon=${longitude}`);
        if (!response.ok) throw new Error("Reverse geocoding failed");
        const data = await response.json();
        position.placeName = data.display_name || "Selected farm location";
      } catch (error) {
        position.placeName = "Selected farm location";
      }
      return position.placeName;
    }

    async function showLocationUsed(position) {
      const source = position.source === "map" ? "Confirmed farm map location" : "Browser GPS location";
      const placeName = await getPlaceName(position);
      const accuracy = Number(position.coords.accuracy);
      const accuracyText = Number.isFinite(accuracy) && accuracy > 0
        ? ` (about ${Math.round(accuracy)} m accuracy)`
        : "";
      const correctionText = position.source === "map"
        ? ""
        : " If the village name is not yours, choose your farm on the map.";
      locationUsed.textContent = `Location used: ${source} - ${placeName}${accuracyText}.${correctionText}`;
    }

    function setFarmMarker(latitude, longitude, accuracy = 0, source = "map") {
      const lat = Number(latitude);
      const lng = Number(longitude);
      const safeAccuracy = Number.isFinite(Number(accuracy)) ? Number(accuracy) : 0;

      if (farmMarker) farmMarker.setLatLng([lat, lng]);
      else farmMarker = L.circleMarker([lat, lng], {
        radius: 10,
        color: "#ffffff",
        weight: 3,
        fillColor: "#d34b32",
        fillOpacity: 1
      }).addTo(farmMap);

      if (safeAccuracy > 0 && farmAccuracyCircle) {
        farmAccuracyCircle.setLatLng([lat, lng]);
        farmAccuracyCircle.setRadius(safeAccuracy);
      } else if (safeAccuracy > 0) {
        farmAccuracyCircle = L.circle([lat, lng], {
          radius: safeAccuracy,
          color: "#2d8c7d",
          weight: 1,
          fillColor: "#8ec9bb",
          fillOpacity: 0.18
        }).addTo(farmMap);
      }

      pendingFarmLocation = {
        coords: { latitude: lat, longitude: lng, accuracy: safeAccuracy },
        source
      };
      farmMapSelection.textContent = source === "gps"
        ? "GPS location selected. Check the marker, then confirm it."
        : "Farm location selected. Click Confirm location to save it.";
    }

    function openFarmMap() {
      if (!window.L) {
        statusBox.textContent = "The map could not load. Check your internet connection and try again.";
        return;
      }
      farmLocationDialog.showModal();
      pendingFarmLocation = selectedFarmLocation;
      const defaultLocation = [12.9951, 76.0882];
      if (!farmMap) {
        farmMap = L.map("farmMap").setView(defaultLocation, 10);
        L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
          maxZoom: 19,
          attribution: "Tiles Â© Esri"
        }).addTo(farmMap);
        L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
          maxZoom: 19,
          attribution: "Labels Â© Esri",
          opacity: 0.9
        }).addTo(farmMap);
        farmMap.on("click", (event) => setFarmMarker(event.latlng.lat, event.latlng.lng));
      }
      if (selectedFarmLocation) {
        const { latitude, longitude } = selectedFarmLocation.coords;
        pendingFarmLocation = selectedFarmLocation;
        setFarmMarker(latitude, longitude);
        farmMap.setView([latitude, longitude], 15);
      } else {
        if (farmMarker) {
          farmMap.removeLayer(farmMarker);
          farmMarker = null;
        }
        farmMapSelection.textContent = "No farm location selected yet.";
      }
      setTimeout(() => farmMap.invalidateSize(), 0);
      getCurrentLocation()
        .then((position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          setFarmMarker(lat, lon, position.coords.accuracy || 25, "gps");
          farmMap.setView([lat, lon], 16);
        })
        .catch(() => {});
    }

    function showLocationPermissionHelp() {
      nearestMarket.textContent = "Location needed";
      nearestMarketDetails.textContent = "Allow location access in site controls beside the address bar, or use Choose Farm on Map to select your exact farm location.";
      statusBox.textContent = "";
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      statusBox.textContent = "";
      setBusy(true);

      try {
        const data = await postJson("/predict-from-dataset", getInputPayload());
        showReadingSource(data.today_date);
        predictedPrice.textContent = formatQuintalPrice(data.predicted_price);
        predictionDetails.textContent = `${data.crop_name} in ${data.market_name} after ${data.forecast_days} day(s).${formatForecastSeries(data.features_used?.forecast_series)}`;
        showForecastChange(data);
      } catch (error) {
        statusBox.textContent = `Backend error: ${error.message}`;
      } finally {
        setBusy(false);
      }
    });

    bestMarketButton.addEventListener("click", async () => {
      statusBox.textContent = "";
      setBusy(true);

      try {
        statusBox.textContent = "Comparing predicted prices across markets...";
        const data = await postJson("/best-market-from-dataset", getInputPayload());
        const best = data.all_predictions[0];
        bestMarket.textContent = best.market_name;
        bestMarketDetails.textContent = `${formatQuintalPrice(best.predicted_price)} forecast after ${data.forecast_days} day(s).${data.second_best_market ? ` Advantage over ${data.second_best_market}: ${formatQuintalPrice(data.price_advantage)}.` : ""}`;
        marketList.innerHTML = data.all_predictions
          .map((item) => `
            <tr class="${item.market_name === best.market_name ? "best" : ""}">
              <td>${item.market_name}</td>
              <td>${formatQuintalPrice(item.predicted_price)}</td>
              <td>${formatQuintalPrice(item.last_price)}</td>
            </tr>
          `)
          .join("");

        statusBox.textContent = "";
      } catch (error) {
        statusBox.textContent = error.message || "Could not compare markets. Check that uvicorn is still running.";
      } finally {
        setBusy(false);
      }
    });

    nearestMarketButton.addEventListener("click", async () => {
      statusBox.textContent = "";
      setBusy(true);

      try {
        statusBox.textContent = "Getting a precise location and comparing price with road distance...";
        const manualLocation = getFarmLocation();
        const position = manualLocation || await getCurrentLocation();
        await showLocationUsed(position);
        statusBox.textContent = "Location received. Comparing markets...";
        const data = await postJson("/nearest-market-with-best-price", getTransportPayload(position));
        const nearest = data.nearest_market;
        const recommended = data.best_market_after_transport;
        const gpsAccuracy = Number(data.location_accuracy_m);
        const accuracyText = position.source === "map"
          ? " Distance uses the farm coordinates you entered."
          : Number.isFinite(gpsAccuracy) && gpsAccuracy > 0
          ? gpsAccuracy > 500
          ? ` GPS accuracy is about ${Math.round(gpsAccuracy)} m; use Choose Farm on Map for a more exact result.`
          : ` Your location accuracy was about ${Math.round(gpsAccuracy)} m.`
          : "";

        nearestMarket.textContent = recommended.market_name;
        nearestMarketDetails.textContent = `${formatQuintalPrice(recommended.predicted_price)} forecast âˆ’ ${formatQuintalPrice(recommended.transport_cost_per_quintal)} transport = ${formatQuintalPrice(recommended.net_return_per_quintal)} net return (using â‚¹${data.transport_cost_per_km_quintal.toFixed(2)}/km/quintal). ${recommended.distance_km.toFixed(1)} km by road to recommended ${recommended.market_name}. Closest APMC: ${nearest.market_name} (${nearest.distance_km.toFixed(1)} km by road).${accuracyText}`;
        statusBox.textContent = "";
      } catch (error) {
        if (error.message === "LOCATION_UNAVAILABLE" || error.message === "LOCATION_PERMISSION_DENIED") {
          showLocationPermissionHelp();
          if (error.message === "LOCATION_PERMISSION_DENIED") {
            statusBox.textContent = "Location permission was denied. Allow location access in the browser, or choose your farm on the map.";
          }
        } else {
          statusBox.textContent = error.message || "Could not compare price and distance. Check that uvicorn is still running.";
        }
      } finally {
        setBusy(false);
      }
    });

    farmMapButton.addEventListener("click", openFarmMap);
    document.getElementById("closeForecastChangeButton").addEventListener("click", () => forecastChangeDialog.close());
    useGpsLocationButton.addEventListener("click", async () => {
      useGpsLocationButton.disabled = true;
      locationUsed.textContent = "Getting your current GPS location...";
      try {
        const position = await getCurrentLocation();
        position.source = "gps";
        selectedFarmLocation = position;
        setFarmMarker(position.coords.latitude, position.coords.longitude, position.coords.accuracy || 25, "gps");
        farmMap.setView([position.coords.latitude, position.coords.longitude], 17);
        await showLocationUsed(position);
        statusBox.textContent = "Current GPS location selected. Click Find Best Market by Price & Distance.";
      } catch (error) {
        locationUsed.textContent = error.message === "LOCATION_PERMISSION_DENIED"
          ? "GPS permission denied. Allow location access in the browser."
          : "GPS location unavailable. Choose Farm on Map instead.";
        statusBox.textContent = "Could not get your current GPS location.";
      } finally {
        useGpsLocationButton.disabled = false;
      }
    });
    useCurrentLocationButton.addEventListener("click", async () => {
      useCurrentLocationButton.disabled = true;
      farmMapSelection.textContent = "Finding your current location...";
      try {
        const position = await getCurrentLocation();
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        setFarmMarker(lat, lon, position.coords.accuracy || 25, "gps");
        position.source = "gps";
        pendingFarmLocation = position;
        farmMap.setView([lat, lon], 17);
        farmMapSelection.textContent = "GPS location selected. Check the marker, then confirm it.";
      } catch (error) {
        farmMapSelection.textContent = error.message === "LOCATION_PERMISSION_DENIED"
          ? "Location access was denied. Allow it in the browser or search for your village."
          : "Could not get your location. Search for your village or tap the farm on the map.";
      } finally {
        useCurrentLocationButton.disabled = false;
      }
    });
    document.getElementById("farmSearchButton").addEventListener("click", async () => {
      const query = farmSearchInput.value.trim();
      if (!query) {
        farmMapSelection.textContent = "Enter a village, taluk, or nearby landmark to search.";
        return;
      }

      farmMapSelection.textContent = "Finding the location on the map...";
      farmSearchResults.replaceChildren();
      try {
        // Farmers commonly write names such as "Village, Hassan (taluk)".
        // Remove that extra punctuation before looking up the village.
        const normalizedQuery = query
          .replace(/[()]/g, " ")
          .replace(/\b(taluk|taluka)\b/gi, " ")
          .replace(/\s*,\s*/g, ", ")
          .replace(/\s+/g, " ")
          .trim();
        // Try common local spelling variants. For example, users may type
        // "Mosalehosalli" while mapping data records "Mosalehosahalli".
        const villageVariants = [...new Set([
          normalizedQuery,
          normalizedQuery.replace(/hosalli\b/gi, "hosahalli"),
          normalizedQuery.replace(/hosahalli\b/gi, "hosalli"),
          normalizedQuery.replace(/\b(village|grama|gram panchayat|panchayat)\b/gi, "").trim(),
          normalizedQuery.replace(/\s+district\b/gi, "")
        ].filter(Boolean))];
        const includesHassan = /\bhassan\b/i.test(normalizedQuery);
        const geocoderContexts = [
          includesHassan ? "Hassan, Karnataka, India" : "Karnataka, India",
          includesHassan ? "Hassan District, Karnataka, India" : "Karnataka, India",
          "Hassan taluk, Karnataka, India",
          "Karnataka, India"
        ];
        const searchQueries = [...new Set(villageVariants.flatMap((village) => [
          ...geocoderContexts.map((context) => `${village}, ${context}`),
          ...geocoderContexts.map((context) => `${village} ${context}`),
          village
        ].filter(Boolean)))];

        let results = [];
        const seenResults = new Map();
        const pushResult = (result) => {
          const lat = Number(result.lat ?? result.latitude);
          const lon = Number(result.lon ?? result.longitude);
          const displayName = result.display_name || result.name || result.address?.village || normalizedQuery;
          const key = `${lat.toFixed(6)},${lon.toFixed(6)},${displayName}`;
          if (!Number.isFinite(lat) || !Number.isFinite(lon) || seenResults.has(key)) {
            return;
          }
          seenResults.set(key, { ...result, lat: String(lat), lon: String(lon), display_name: displayName });
        };

        for (const searchQuery of searchQueries) {
          const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=12&countrycodes=in&accept-language=en&q=${encodeURIComponent(searchQuery)}`);
          if (!response.ok) continue;
          const matches = await response.json();
          if (!matches.length) continue;
          matches.forEach(pushResult);
          if (seenResults.size >= 24) break;
        }

        // Photon has a separate village and landmark index. It is a useful
        // fallback for small villages, alternate spellings, and gram panchayat
        // names that are not returned by the first search service.
        if (seenResults.size < 12) {
          const photonQueries = [...new Set([
            `${villageVariants[0]}, Karnataka, India`,
            includesHassan ? `${villageVariants[0]}, Hassan District, Karnataka, India` : `${villageVariants[0]}, Karnataka, India`,
            `${villageVariants[0]}`
          ])];

          for (const photonQuery of photonQueries) {
            const photonResponse = await fetch(`https://photon.komoot.io/api/?limit=12&lang=en&q=${encodeURIComponent(photonQuery)}`);
            if (!photonResponse.ok) continue;
            const photonData = await photonResponse.json();
            const photonMatches = (photonData.features || [])
              .filter((feature) => Array.isArray(feature.geometry?.coordinates))
              .map((feature) => {
                const [longitude, latitude] = feature.geometry.coordinates;
                const place = feature.properties || {};
                const displayName = [
                  place.name,
                  place.locality,
                  place.city,
                  place.district,
                  place.state,
                  place.country
                ].filter(Boolean).join(", ");
                return {
                  lat: String(latitude),
                  lon: String(longitude),
                  display_name: displayName || normalizedQuery
                };
              });
            photonMatches.forEach(pushResult);
            if (seenResults.size >= 24) break;
          }
        }

        results = [...seenResults.values()]
          .sort((a, b) => rankSearchResult(normalizedQuery, b) - rankSearchResult(normalizedQuery, a))
          .slice(0, 24);
        if (!results.length) {
          throw new Error("No location found");
        }
        results.forEach((result) => {
          const resultButton = document.createElement("button");
          resultButton.type = "button";
          resultButton.className = "map-search-result";
          resultButton.textContent = result.display_name;
          resultButton.addEventListener("click", () => {
            const lat = Number(result.lat);
            const lon = Number(result.lon);
            setFarmMarker(lat, lon, 25, "map");
            farmMap.setView([lat, lon], 16);
            farmMapSelection.textContent = `Showing ${result.display_name}. Zoom or pan if needed, then tap your exact farm.`;
            farmSearchResults.replaceChildren();
          });
          farmSearchResults.appendChild(resultButton);
        });
        farmMapSelection.textContent = `${results.length} matching locations found. Choose your village or landmark from the list.`;
      } catch (error) {
        farmMapSelection.textContent = "Location not found. Try the village name with its taluk or district.";
      }
    });
    farmSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        document.getElementById("farmSearchButton").click();
      }
    });
    document.getElementById("cancelFarmMapButton").addEventListener("click", () => farmLocationDialog.close());
    document.getElementById("saveFarmMapButton").addEventListener("click", async () => {
      if (!pendingFarmLocation) {
        farmMapSelection.textContent = "Please tap your farm on the map first.";
        return;
      }
      selectedFarmLocation = {
        coords: { ...pendingFarmLocation.coords },
        source: pendingFarmLocation.source || "map"
      };
      await showLocationUsed(selectedFarmLocation);
      farmMapSelection.textContent = "Farm location confirmed.";
      farmLocationDialog.close();
      statusBox.textContent = "Farm location confirmed. Click Find Best Market by Price & Distance.";
    });

    showReadingSource(new Date().toISOString().slice(0, 10));
    loadMetadata();
  
