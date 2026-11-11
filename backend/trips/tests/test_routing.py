from datetime import UTC, datetime, timedelta

import pytest

from trips.services import routing
from trips.services.checkpoints import path_between, position_at, sample_checkpoints, thin_route
from trips.services.errors import UpstreamError
from trips.services.routing import Route, find_routes, parse_route

DEPARTURE = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
ORIGIN = (40.0, -100.0)
DESTINATION = (40.0, -96.0)


def straight_route(miles=100.0, mph=50.0):
    return Route(
        points=[(40.0, -100.0), (40.0, -99.0)],
        miles=[0.0, miles],
        seconds=[0.0, miles / mph * 3600],
    )


def leg(points):
    return {"points": [{"latitude": lat, "longitude": lon} for lat, lon in points]}


def tomtom_route(*legs, progress=None, duration=600):
    payload = {
        "summary": {"travelTimeInSeconds": duration, "lengthInMeters": 10_000},
        "legs": [leg(points) for points in legs],
    }
    if progress:
        payload["progress"] = progress
    return payload


def road(lat, count=10):
    return [(lat, -100.0 + 4.0 * step / count) for step in range(count + 1)]


def test_progress_entries_set_the_drive_time_of_their_stretches():
    points = [(40.0, -100.0), (40.0, -99.9), (40.0, -99.8), (40.0, -99.7)]
    route = parse_route(
        tomtom_route(
            points,
            progress=[
                {"pointIndex": 0, "travelTimeInSeconds": 0},
                {"pointIndex": 2, "travelTimeInSeconds": 100},
                {"pointIndex": 3, "travelTimeInSeconds": 1000},
            ],
        )
    )
    assert route.seconds[1] == pytest.approx(50, abs=0.5)
    assert route.seconds[2] == pytest.approx(100)
    assert route.seconds[3] == pytest.approx(1000)


def test_progress_entries_without_a_time_are_ignored():
    points = [(40.0, -100.0), (40.0, -99.9), (40.0, -99.8)]
    route = parse_route(
        tomtom_route(
            points,
            progress=[
                {"pointIndex": 0, "travelTimeInSeconds": 0},
                {"pointIndex": 1, "distanceInMeters": 8000},
                {"pointIndex": 2, "travelTimeInSeconds": 200},
            ],
        )
    )
    assert route.seconds[1] == pytest.approx(100, abs=0.5)


def test_time_is_spread_by_distance_without_progress():
    points = [(40.0, -100.0), (40.0, -99.9), (40.0, -99.7)]
    route = parse_route(tomtom_route(points, duration=300))
    assert route.seconds[1] == pytest.approx(100, abs=0.5)
    assert route.seconds[2] == pytest.approx(300)


def test_progress_indexes_line_up_across_legs():
    first = [(40.0, -100.0), (40.0, -99.9)]
    second = [(40.0, -99.9), (40.0, -99.8)]
    route = parse_route(
        tomtom_route(
            first,
            second,
            progress=[
                {"pointIndex": 0, "travelTimeInSeconds": 0},
                {"pointIndex": 2, "travelTimeInSeconds": 100},
                {"pointIndex": 3, "travelTimeInSeconds": 400},
            ],
        )
    )
    assert len(route.points) == 4
    assert route.miles[1] == pytest.approx(route.miles[2])
    assert route.seconds[-1] == pytest.approx(400)


def test_position_is_interpolated_along_a_segment():
    point, seconds = position_at(straight_route(), 50)
    assert point == pytest.approx((40.0, -99.5))
    assert seconds == pytest.approx(3600)


def test_position_at_the_very_end_of_the_route():
    point, seconds = position_at(straight_route(), 100)
    assert point == pytest.approx((40.0, -99.0))
    assert seconds == pytest.approx(7200)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoints_cover_the_route_at_each_interval(interval):
    checkpoints = sample_checkpoints(straight_route(miles=107), interval, DEPARTURE)
    assert checkpoints[0].mile == 0
    assert checkpoints[1].mile == interval
    assert checkpoints[-1].mile == 107
    assert checkpoints[-1].mile - checkpoints[-2].mile <= interval


def test_checkpoint_eta_uses_arrival_time_not_departure():
    checkpoints = sample_checkpoints(straight_route(), 50, DEPARTURE)
    assert checkpoints[0].eta == DEPARTURE
    assert checkpoints[1].eta == DEPARTURE + timedelta(hours=1)
    assert checkpoints[2].eta == DEPARTURE + timedelta(hours=2)


def test_path_between_is_cut_at_both_miles():
    route = Route(
        points=[(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)],
        miles=[0.0, 10.0, 20.0],
        seconds=[0.0, 10.0, 20.0],
    )
    assert path_between(route, 5, 15) == [(0.0, 0.5), (0.0, 1.0), (0.0, 1.5)]


def stop_count(url):
    return url.split("/calculateRoute/")[1].split("/")[0].count(":") + 1


def fake_router(monkeypatch, direct, via_routes=()):
    remaining = list(via_routes)

    def fake_get_json(url, params, service_name):
        if stop_count(url) == 3:
            return {"routes": [remaining.pop(0)] if remaining else []}
        return {"routes": direct}

    monkeypatch.setattr(routing, "get_json", fake_get_json)


def route_payload(lat):
    return tomtom_route(road(lat))


def test_three_routes_from_the_router_need_no_fallback(monkeypatch):
    fake_router(monkeypatch, [route_payload(40.0), route_payload(40.5), route_payload(41.0)])
    assert len(find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)) == 3


def test_missing_alternatives_are_filled_with_via_routes(monkeypatch):
    fake_router(monkeypatch, [route_payload(40.0)], [route_payload(40.5), route_payload(41.0)])
    assert len(find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)) == 3


def test_via_routes_on_the_same_road_are_rejected(monkeypatch):
    fake_router(
        monkeypatch,
        [route_payload(40.0)],
        [route_payload(40.0), route_payload(40.5), route_payload(40.5), route_payload(41.0)],
    )
    routes = find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)
    assert len(routes) == 3
    assert [round(route.points[0][0], 1) for route in routes] == [40.0, 40.5, 41.0]


def test_no_route_at_all_is_an_error(monkeypatch):
    fake_router(monkeypatch, [])
    with pytest.raises(routing.NoRouteFound):
        find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)


def test_router_request_describes_the_truck_and_trip(monkeypatch):
    seen = {}

    def fake_get_json(url, params, service_name):
        seen.update(params, url=url)
        return {"routes": [route_payload(40.0), route_payload(40.5), route_payload(41.0)]}

    monkeypatch.setattr(routing, "get_json", fake_get_json)
    find_routes(ORIGIN, DESTINATION, DEPARTURE, 40_000)
    assert seen["vehicleWeight"] == 18144
    assert seen["travelMode"] == "truck"
    assert seen["vehicleMaxSpeed"] == routing.TRUCK_MAX_SPEED_KMH
    assert seen["maxAlternatives"] == 2
    assert seen["departAt"] == "2026-11-10T08:00:00Z"
    assert "travelTime" in seen["extendedRouteRepresentation"]
    assert "/calculateRoute/40.00000,-100.00000:40.00000,-96.00000/json" in seen["url"]


def test_unconnected_places_are_reported_as_no_route(monkeypatch):
    def fake_get_json(url, params, service_name):
        raise UpstreamError("unavailable", status_code=400)

    monkeypatch.setattr(routing, "get_json", fake_get_json)
    with pytest.raises(routing.NoRouteFound):
        find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)


def test_a_router_outage_is_not_reported_as_no_route(monkeypatch):
    def fake_get_json(url, params, service_name):
        raise UpstreamError("unavailable", status_code=503)

    monkeypatch.setattr(routing, "get_json", fake_get_json)
    with pytest.raises(UpstreamError):
        find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)


def test_unroutable_via_points_are_skipped(monkeypatch):
    payloads = [route_payload(40.5), route_payload(41.0)]

    def fake_get_json(url, params, service_name):
        if stop_count(url) == 2:
            return {"routes": [route_payload(40.0)]}
        if len(payloads) == 2 and not getattr(fake_get_json, "failed", False):
            fake_get_json.failed = True
            raise UpstreamError("unavailable", status_code=400)
        return {"routes": [payloads.pop(0)]}

    monkeypatch.setattr(routing, "get_json", fake_get_json)
    assert len(find_routes(ORIGIN, DESTINATION, DEPARTURE, 30_000)) == 3


def test_thinning_keeps_ends_and_original_mileage():
    route = Route(
        points=[(0.0, x / 100) for x in range(11)],
        miles=[float(x) for x in range(11)],
        seconds=[x * 60.0 for x in range(11)],
    )
    thin = thin_route(route, 3)
    assert thin.points[0] == route.points[0]
    assert thin.points[-1] == route.points[-1]
    assert thin.miles == [0.0, 3.0, 6.0, 9.0, 10.0]
    assert thin.seconds == [0.0, 180.0, 360.0, 540.0, 600.0]
