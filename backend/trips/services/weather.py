import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.core.cache import cache

from .http import get_json
from .risk import Weather

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 10
CACHE_SECONDS = 60 * 60
BATCH_SIZE = 100
SECONDS_PER_HOUR = 3600

# About 7 miles, so neighbouring checkpoints at the 10 mile interval stay separate.
GRID_DEGREES = 0.1


@dataclass(frozen=True)
class Forecast:
    start: int
    wind_mph: list
    rain_in_hr: list
    snow_in_hr: list

    def at(self, moment):
        """Return the weather at a moment, or None when the forecast doesn't cover it.

        Wind is an instantaneous value at each hour, so it is interpolated. Rain and snow are
        totals for the hour ending at the timestamp, so a moment reads from the hour it falls in.
        """
        offset = (moment.timestamp() - self.start) / SECONDS_PER_HOUR
        before = math.floor(offset)
        after = math.ceil(offset)
        if before < 0 or after >= len(self.wind_mph):
            return None

        wind_before, wind_after = self.wind_mph[before], self.wind_mph[after]
        rain, snow = self.rain_in_hr[after], self.snow_in_hr[after]
        if None in (wind_before, wind_after, rain, snow):
            return None

        wind = wind_before + (wind_after - wind_before) * (offset - before)
        return Weather(wind_mph=wind, rain_in_hr=rain, snow_in_hr=snow)


def grid_cell(lat, lon):
    return (round(lat / GRID_DEGREES) * GRID_DEGREES, round(lon / GRID_DEGREES) * GRID_DEGREES)


def _cache_key(cell):
    return f"forecast:{cell[0]:.1f}:{cell[1]:.1f}"


def _sum_rain(rain, showers):
    return [None if a is None or b is None else a + b for a, b in zip(rain, showers)]


def _parse_forecast(payload):
    hourly = payload["hourly"]
    return Forecast(
        start=hourly["time"][0],
        wind_mph=hourly["wind_speed_10m"],
        # "rain" only covers large scale systems. Convective rain is reported as "showers".
        rain_in_hr=_sum_rain(hourly["rain"], hourly["showers"]),
        # precipitation_unit=inch converts snowfall as well (checked against the metric response).
        snow_in_hr=hourly["snowfall"],
    )


def _fetch_batch(cells):
    payload = get_json(
        FORECAST_URL,
        {
            "latitude": ",".join(f"{cell[0]:.1f}" for cell in cells),
            "longitude": ",".join(f"{cell[1]:.1f}" for cell in cells),
            "hourly": "wind_speed_10m,rain,showers,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timeformat": "unixtime",
            "forecast_days": FORECAST_DAYS,
        },
        "The weather service",
    )
    # A single location comes back as an object rather than a one item list.
    items = payload if isinstance(payload, list) else [payload]
    return {cell: _parse_forecast(item) for cell, item in zip(cells, items)}


def get_forecasts(coordinates):
    """Return {grid cell: Forecast} for every grid cell touched by the coordinates."""
    cells = {grid_cell(lat, lon) for lat, lon in coordinates}
    keys = {_cache_key(cell): cell for cell in cells}

    cached = cache.get_many(keys)
    forecasts = {keys[key]: forecast for key, forecast in cached.items()}

    missing = sorted(cells - forecasts.keys())
    batches = [missing[start : start + BATCH_SIZE] for start in range(0, len(missing), BATCH_SIZE)]
    if batches:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for fetched in pool.map(_fetch_batch, batches):
                forecasts.update(fetched)
                cache.set_many(
                    {_cache_key(cell): forecast for cell, forecast in fetched.items()},
                    CACHE_SECONDS,
                )

    return forecasts


def weather_at(forecasts, lat, lon, moment):
    return forecasts[grid_cell(lat, lon)].at(moment)
