from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from trips.services import weather
from trips.services.weather import Forecast, get_forecasts, grid_cell

START = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)


def forecast(wind=(10, 20, 30), rain=(0.0, 0.1, 0.3), snow=(0.0, 0.5, 1.0)):
    return Forecast(
        start=int(START.timestamp()),
        wind_mph=list(wind),
        rain_in_hr=list(rain),
        snow_in_hr=list(snow),
    )


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def test_exact_hour_reads_that_hour():
    result = forecast().at(START + timedelta(hours=1))
    assert result.wind_mph == 20
    assert result.rain_in_hr == 0.1
    assert result.snow_in_hr == 0.5


def test_wind_is_interpolated_between_hours():
    assert forecast().at(START + timedelta(minutes=90)).wind_mph == pytest.approx(25)


def test_rain_and_snow_read_the_hour_the_moment_falls_in():
    result = forecast().at(START + timedelta(minutes=90))
    assert result.rain_in_hr == 0.3
    assert result.snow_in_hr == 1.0


def test_moment_outside_the_forecast_has_no_weather():
    assert forecast().at(START - timedelta(minutes=1)) is None
    assert forecast().at(START + timedelta(minutes=121)) is None


def test_gaps_in_the_forecast_are_reported_as_no_weather():
    assert forecast(rain=(0.0, None, 0.3)).at(START + timedelta(hours=1)) is None


def api_location(wind=5.0, rain=0.1, showers=0.2, snow=0.0):
    return {
        "hourly": {
            "time": [int(START.timestamp())],
            "wind_speed_10m": [wind],
            "rain": [rain],
            "showers": [showers],
            "snowfall": [snow],
        }
    }


def test_rain_includes_showers(monkeypatch):
    monkeypatch.setattr(weather, "get_json", lambda *args: api_location())
    forecasts = get_forecasts([(40.0, -100.0)])
    assert forecasts[grid_cell(40.0, -100.0)].rain_in_hr[0] == pytest.approx(0.3)


def test_nearby_coordinates_share_one_lookup_and_the_cache_is_used(monkeypatch):
    calls = []

    def fake_get_json(url, params, service_name):
        calls.append(params["latitude"])
        return api_location()

    monkeypatch.setattr(weather, "get_json", fake_get_json)

    get_forecasts([(40.01, -100.01), (40.02, -100.02)])
    get_forecasts([(40.01, -100.01)])
    assert calls == ["40.0"]


def test_large_requests_are_split_into_batches(monkeypatch):
    sizes = []

    def fake_get_json(url, params, service_name):
        count = len(params["latitude"].split(","))
        sizes.append(count)
        return [api_location() for _ in range(count)]

    monkeypatch.setattr(weather, "get_json", fake_get_json)

    coordinates = [(30 + index * 0.1, -100.0) for index in range(250)]
    assert len(get_forecasts(coordinates)) == 250
    assert sorted(sizes) == [50, 100, 100]


def test_results_stay_matched_to_their_coordinates(monkeypatch):
    def fake_get_json(url, params, service_name):
        lats = params["latitude"].split(",")
        return [api_location(wind=float(lat)) for lat in lats]

    monkeypatch.setattr(weather, "get_json", fake_get_json)

    forecasts = get_forecasts([(40.0, -100.0), (41.0, -100.0)])
    assert forecasts[grid_cell(40.0, -100.0)].wind_mph == [40.0]
    assert forecasts[grid_cell(41.0, -100.0)].wind_mph == [41.0]
