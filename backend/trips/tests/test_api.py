from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from trips.api.throttles import TripThrottle
from trips.services import places, routing, weather
from trips.services.errors import UpstreamError
from trips.services.geo import distance_miles
from trips.services.heatmap import CORRIDOR_MILES, HOURS, MAX_POINTS, corridor_cells, corridor_grid

ROUTE_LATS = (40.0, 40.5, 41.0)


def tomtom_route(lat):
    points = [(lat, -100.0 + step * 0.5) for step in range(9)]
    return {
        "summary": {"travelTimeInSeconds": 4 * 3600, "lengthInMeters": 340_000},
        "legs": [{"points": [{"latitude": a, "longitude": b} for a, b in points]}],
    }


def place_result(name="Denver, CO", lat=40.0, lon=-100.0):
    return {"address": {"freeformAddress": name}, "position": {"lat": lat, "lon": lon}}


def forecast_payload(params, wind=10.0, snow=0.0):
    now = int(timezone.now().timestamp()) // 3600 * 3600
    hours = 240
    return [
        {
            "hourly": {
                "time": [now + 3600 * hour for hour in range(hours)],
                "wind_speed_10m": [wind] * hours,
                "rain": [0.0] * hours,
                "showers": [0.0] * hours,
                "snowfall": [snow] * hours,
            }
        }
        for _ in params["latitude"].split(",")
    ]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture(autouse=True)
def external_services(monkeypatch):
    cache.clear()
    monkeypatch.setattr(places, "get_json", lambda url, params, name: {"results": [place_result()]})
    monkeypatch.setattr(
        routing,
        "get_json",
        lambda url, params, name: {"routes": [tomtom_route(lat) for lat in ROUTE_LATS]},
    )
    monkeypatch.setattr(weather, "get_json", lambda url, params, name: forecast_payload(params))


def trip(**overrides):
    return {
        "origin": "Denver, CO",
        "destination": "Omaha, NE",
        "departure_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_lb": 30_000,
        **overrides,
    }


def test_plan_returns_three_assessed_routes(client):
    response = client.post("/api/trips/plan", trip(), format="json")
    assert response.status_code == 200

    body = response.json()
    assert [route["id"] for route in body["routes"]] == ["A", "B", "C"]
    assert body["recommendation"]["is_safe"] is True

    route = body["routes"][0]
    assert route["miles_by_risk"]["low"] == pytest.approx(route["distance_miles"], abs=0.2)
    assert route["checkpoints"][0]["risk"] == "low"
    assert route["checkpoints"][0]["weather"]["wind_mph"] == 10.0
    assert route["segments"][0]["risk"] == "low"


def test_plan_applies_the_load_rule(client, monkeypatch):
    monkeypatch.setattr(
        weather, "get_json", lambda url, params, name: forecast_payload(params, wind=50.0)
    )
    light = client.post("/api/trips/plan", trip(load_lb=30_000), format="json").json()
    assert light["routes"][0]["checkpoints"][0]["risk"] == "severe"
    assert light["recommendation"]["is_safe"] is True

    heavy = client.post("/api/trips/plan", trip(load_lb=30_001), format="json").json()
    assert heavy["routes"][0]["checkpoints"][0]["risk"] == "no_travel"
    assert heavy["recommendation"]["is_safe"] is False


def test_segments_cover_the_whole_route_when_risk_changes(client, monkeypatch):
    def changing_weather(url, params, name):
        payload = forecast_payload(params)
        for location, lon in zip(payload, params["longitude"].split(",")):
            if float(lon) > -98:
                location["hourly"] = {**location["hourly"], "snowfall": [2.5] * 240}
        return payload

    monkeypatch.setattr(weather, "get_json", changing_weather)
    route = client.post("/api/trips/plan", trip(), format="json").json()["routes"][0]

    assert [segment["risk"] for segment in route["segments"]] == ["low", "severe"]
    first, second = route["segments"]
    assert first["path"][-1] == second["path"][0]
    assert first["path"][0] == [40.0, -100.0]
    assert second["path"][-1] == [40.0, -96.0]


def test_interval_changes_the_checkpoint_spacing(client):
    body = client.post("/api/trips/plan", trip(interval_miles=50), format="json").json()
    checkpoints = body["routes"][0]["checkpoints"]
    assert checkpoints[1]["mile"] - checkpoints[0]["mile"] == pytest.approx(50, abs=0.2)


@pytest.mark.parametrize(
    "field, value",
    [
        ("load_lb", 0),
        ("load_lb", -5),
        ("interval_miles", 30),
        ("origin", ""),
        ("departure_at", "not a date"),
    ],
)
def test_plan_rejects_bad_input(client, field, value):
    response = client.post("/api/trips/plan", trip(**{field: value}), format="json")
    assert response.status_code == 400
    assert field in response.json()


def test_plan_rejects_a_departure_in_the_past(client):
    past = (timezone.now() - timedelta(hours=2)).isoformat()
    response = client.post("/api/trips/plan", trip(departure_at=past), format="json")
    assert response.status_code == 400


def test_plan_rejects_a_departure_beyond_the_forecast(client):
    future = (timezone.now() + timedelta(days=8)).isoformat()
    response = client.post("/api/trips/plan", trip(departure_at=future), format="json")
    assert response.status_code == 400


def test_unknown_place_gets_a_readable_error(client, monkeypatch):
    monkeypatch.setattr(places, "get_json", lambda url, params, name: {"results": []})
    response = client.post("/api/trips/plan", trip(), format="json")
    assert response.status_code == 422
    assert "Denver" in response.json()["detail"]


def test_upstream_failure_gets_a_readable_error(client, monkeypatch):
    def fail(url, params, name):
        raise UpstreamError("The weather service is unavailable. Please try again.")

    monkeypatch.setattr(weather, "get_json", fail)
    response = client.post("/api/trips/plan", trip(), format="json")
    assert response.status_code == 502
    assert "weather" in response.json()["detail"]


def test_heatmap_has_a_value_for_every_hour(client):
    response = client.post(
        "/api/trips/heatmap",
        {
            "departure_at": trip()["departure_at"],
            "load_lb": 30_000,
            "paths": [[[40.0, -100.0], [40.0, -99.0]]],
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["points"]
    assert all(len(point["risk"]) == HOURS + 1 for point in body["points"])
    assert body["points"][0]["risk"][0] == 0


def test_heatmap_marks_hours_past_the_forecast_as_unknown(client, monkeypatch):
    def short_forecast(url, params, name):
        payload = forecast_payload(params)
        for location in payload:
            location["hourly"] = {key: values[:10] for key, values in location["hourly"].items()}
        return payload

    monkeypatch.setattr(weather, "get_json", short_forecast)
    body = client.post(
        "/api/trips/heatmap",
        {
            "departure_at": trip()["departure_at"],
            "load_lb": 30_000,
            "paths": [[[40.0, -100.0]]],
        },
        format="json",
    ).json()
    assert body["points"][0]["risk"][-1] is None


def test_corridor_stays_within_range_of_the_path():
    path = [(40.0, -100.0), (40.0, -99.0), (40.0, -98.0)]
    cells = corridor_cells([path], step_miles=20)
    assert cells
    assert all(
        min(distance_miles(cell, point) for point in path) <= CORRIDOR_MILES for cell in cells
    )


def test_corridor_grid_stays_near_its_cap_when_routes_split():
    north = [(41.5, -104.0 + step * 0.5) for step in range(36)]
    middle = [(39.7, -104.0 + step * 0.5) for step in range(36)]
    south = [(38.0, -104.0 + step * 0.5) for step in range(36)]
    _, cells = corridor_grid([north, middle, south])
    assert len(cells) <= MAX_POINTS * 1.3


def test_place_search_is_not_limited_to_one_region(client, monkeypatch):
    seen = []

    def fake_get_json(url, params, name):
        seen.append(params)
        return {"results": [place_result("Nagpur, Maharashtra", 21.1, 79.1)]}

    monkeypatch.setattr(places, "get_json", fake_get_json)
    client.post("/api/trips/plan", trip(origin="Nagpur", destination="Pune"), format="json")
    client.get("/api/places", {"q": "Nagpur"})
    assert seen
    assert all("countrySet" not in params for params in seen)


def test_place_names_are_escaped_in_the_url(monkeypatch):
    urls = []

    def fake_get_json(url, params, name):
        urls.append(url)
        return {"results": [place_result()]}

    monkeypatch.setattr(places, "get_json", fake_get_json)
    places.geocode("Denver, CO/80202")
    assert urls[0].endswith("/search/2/geocode/Denver%2C%20CO%2F80202.json")


def test_repeat_lookups_use_the_cache(monkeypatch):
    calls = []

    def fake_get_json(url, params, name):
        calls.append(url)
        return {"results": [place_result()]}

    monkeypatch.setattr(places, "get_json", fake_get_json)
    assert places.geocode("Denver").name == places.geocode(" denver ").name
    assert places.suggest("den") == places.suggest("DEN") == ["Denver, CO"]
    assert len(calls) == 2


def test_suggestions_drop_duplicates(monkeypatch):
    monkeypatch.setattr(
        places,
        "get_json",
        lambda url, params, name: {"results": [place_result("Pune"), place_result("Pune")]},
    )
    assert places.suggest("pun") == ["Pune"]


def heatmap_request(paths):
    return {"departure_at": trip()["departure_at"], "load_lb": 30_000, "paths": paths}


def test_heatmap_rejects_an_impossible_latitude(client):
    response = client.post(
        "/api/trips/heatmap", heatmap_request([[[120.0, -100.0]]]), format="json"
    )
    assert response.status_code == 400
    assert "paths" in response.json()


def test_heatmap_rejects_points_scattered_far_beyond_a_trip(client):
    scattered = [
        [-60.0 + row * 3.0, -170.0 + column * 4.0] for row in range(40) for column in range(12)
    ]
    response = client.post("/api/trips/heatmap", heatmap_request([scattered]), format="json")
    assert response.status_code == 422
    assert "too large" in response.json()["detail"]


def test_requests_beyond_the_rate_limit_are_refused(client, monkeypatch):
    monkeypatch.setattr(TripThrottle, "THROTTLE_RATES", {"trips": "2/min"})
    statuses = [client.post("/api/trips/plan", trip(), format="json").status_code for _ in range(3)]
    assert statuses == [200, 200, 429]


def test_plan_reports_whether_the_forecast_covers_the_route(client):
    body = client.post("/api/trips/plan", trip(), format="json").json()
    assert body["recommendation"]["is_complete"] is True
