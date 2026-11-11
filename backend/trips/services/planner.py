from dataclasses import dataclass

from .checkpoints import path_between, sample_checkpoints, thin_route
from .places import geocode
from .recommend import recommend, summarize
from .risk import classify
from .routing import find_routes
from .weather import get_forecasts, weather_at

ROUTE_LABELS = "ABC"

# Enough detail for the map without sending every point the router returns.
DISPLAY_SPACING_MILES = 0.4


@dataclass(frozen=True)
class AssessedCheckpoint:
    checkpoint: object
    weather: object
    risk: object


def _assess(checkpoints, forecasts, load_lb):
    assessed = []
    for checkpoint in checkpoints:
        weather = weather_at(forecasts, checkpoint.lat, checkpoint.lon, checkpoint.eta)
        risk = None if weather is None else classify(weather, load_lb)
        assessed.append(AssessedCheckpoint(checkpoint, weather, risk))
    return assessed


def build_segments(route, assessed):
    """Split the route where the risk changes, using the same halfway boundaries as the mileage."""
    display = thin_route(route, DISPLAY_SPACING_MILES)
    segments = []
    last = len(assessed) - 1
    start_mile = 0.0
    for index, item in enumerate(assessed):
        following = assessed[index + 1].risk if index < last else object()
        if item.risk == following:
            continue
        end_mile = (
            (item.checkpoint.mile + assessed[index + 1].checkpoint.mile) / 2
            if index < last
            else route.miles[-1]
        )
        segments.append({"risk": item.risk, "path": path_between(display, start_mile, end_mile)})
        start_mile = end_mile
    return segments


def _assess_route(label, route, checkpoints, forecasts, load_lb):
    assessed = _assess(checkpoints, forecasts, load_lb)
    summary = summarize(
        label,
        [(item.checkpoint.mile, item.risk) for item in assessed],
        duration_s=route.seconds[-1],
    )
    return {
        "summary": summary,
        "checkpoints": assessed,
        "segments": build_segments(route, assessed),
    }


def plan_trip(origin, destination, departure, load_lb, interval_miles):
    start = geocode(origin)
    end = geocode(destination)
    routes = find_routes(start.coordinates, end.coordinates, departure, load_lb)

    sampled = [sample_checkpoints(route, interval_miles, departure) for route in routes]
    forecasts = get_forecasts(
        (checkpoint.lat, checkpoint.lon) for checkpoints in sampled for checkpoint in checkpoints
    )

    assessed = [
        _assess_route(label, route, checkpoints, forecasts, load_lb)
        for label, route, checkpoints in zip(ROUTE_LABELS, routes, sampled)
    ]

    return {
        "origin": start,
        "destination": end,
        "departure_at": departure,
        "load_lb": load_lb,
        "interval_miles": interval_miles,
        "routes": assessed,
        "recommendation": recommend([route["summary"] for route in assessed]),
    }
