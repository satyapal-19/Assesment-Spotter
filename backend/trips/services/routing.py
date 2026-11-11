import math
from dataclasses import dataclass

from django.conf import settings

from .checkpoints import position_at
from .errors import NoRouteFound, UpstreamError
from .geo import distance_miles, lerp_point
from .http import get_json

ROUTES_NEEDED = 3
KG_PER_LB = 0.45359237

# Without a limit the router drives trucks at the posted car speed, up to 80 mph on some US
# highways, which makes every later ETA too early. This is about 65 mph.
TRUCK_MAX_SPEED_KMH = 105
BAD_REQUEST = 400

# The router only returns alternatives it considers reasonable, which is often fewer than asked
# for. These push a route away from the direct line, as a share of the direct distance.
VIA_OFFSETS = (0.08, -0.08, 0.16, -0.16)

DISTINCT_SAMPLE_COUNT = 40
REFERENCE_SAMPLE_COUNT = 400
DISTINCT_MIN_SHARE = 0.1
SAME_ROAD_MILES = 1.0


@dataclass(frozen=True)
class Route:
    """A drivable path with the running distance and drive time at each of its points."""

    points: list
    miles: list
    seconds: list


def _time_anchors(payload, last_index):
    anchors = [entry for entry in payload.get("progress", []) if "travelTimeInSeconds" in entry]
    if anchors:
        return anchors
    total = payload["summary"]["travelTimeInSeconds"]
    return [
        {"pointIndex": 0, "travelTimeInSeconds": 0},
        {"pointIndex": last_index, "travelTimeInSeconds": total},
    ]


def _seconds_at_points(payload, miles):
    """Fill in the drive time at every point from the router's sparse progress entries."""
    seconds = [0.0] * len(miles)
    anchors = _time_anchors(payload, len(miles) - 1)
    for start, end in zip(anchors, anchors[1:]):
        first, last = start["pointIndex"], end["pointIndex"]
        stretch = miles[last] - miles[first]
        elapsed = end["travelTimeInSeconds"] - start["travelTimeInSeconds"]
        for index in range(first, last + 1):
            share = (miles[index] - miles[first]) / stretch if stretch else 0.0
            seconds[index] = start["travelTimeInSeconds"] + elapsed * share
    return seconds


def parse_route(payload):
    # Legs share their joining point. It stays in the list twice because the router's progress
    # entries count it twice when they index into the points.
    points = [
        (point["latitude"], point["longitude"])
        for leg in payload["legs"]
        for point in leg["points"]
    ]
    miles = [0.0]
    for a, b in zip(points, points[1:]):
        miles.append(miles[-1] + distance_miles(a, b))
    return Route(points=points, miles=miles, seconds=_seconds_at_points(payload, miles))


def _request_routes(stops, departure, load_lb, alternatives=0):
    locations = ":".join(f"{lat:.5f},{lon:.5f}" for lat, lon in stops)
    payload = get_json(
        f"{settings.TOMTOM_BASE_URL}/routing/1/calculateRoute/{locations}/json",
        {
            "key": settings.TOMTOM_API_KEY,
            "travelMode": "truck",
            "vehicleCommercial": "true",
            "vehicleMaxSpeed": TRUCK_MAX_SPEED_KMH,
            "vehicleWeight": round(load_lb * KG_PER_LB),
            "departAt": departure.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "maxAlternatives": alternatives,
            "routeRepresentation": "polyline",
            "extendedRouteRepresentation": ["distance", "travelTime"],
        },
        "The routing service",
    )
    return [parse_route(item) for item in payload.get("routes", [])]


def _resample(route, count):
    total = route.miles[-1]
    return [position_at(route, total * step / count)[0] for step in range(count + 1)]


def _is_distinct(candidate, existing):
    samples = _resample(candidate, DISTINCT_SAMPLE_COUNT)

    for route in existing:
        reference = _resample(route, REFERENCE_SAMPLE_COUNT)
        tolerance = max(SAME_ROAD_MILES, route.miles[-1] / REFERENCE_SAMPLE_COUNT)
        off_road = sum(
            min(distance_miles(sample, point) for point in reference) > tolerance
            for sample in samples
        )
        if off_road / len(samples) < DISTINCT_MIN_SHARE:
            return False
    return True


def _offset_midpoint(origin, destination, share):
    mid = lerp_point(origin, destination, 0.5)
    lat_scale = math.cos(math.radians(mid[0]))
    east = (destination[1] - origin[1]) * lat_scale
    north = destination[0] - origin[0]
    return (mid[0] + east * share, mid[1] - north * share / max(lat_scale, 0.1))


def find_routes(origin, destination, departure, load_lb):
    try:
        routes = _request_routes(
            [origin, destination], departure, load_lb, alternatives=ROUTES_NEEDED - 1
        )
    except UpstreamError as exc:
        # The router answers 400 when no road connects the two places, such as across an ocean.
        if exc.status_code != BAD_REQUEST:
            raise
        routes = []
    if not routes:
        raise NoRouteFound("No truck route was found between these places.")

    routes = routes[:ROUTES_NEEDED]
    for share in VIA_OFFSETS:
        if len(routes) >= ROUTES_NEEDED:
            break
        via = _offset_midpoint(origin, destination, share)
        try:
            candidates = _request_routes([origin, via, destination], departure, load_lb)
        except UpstreamError:
            # A via point can land somewhere unroutable, such as open water. Try the next one.
            continue
        routes.extend(route for route in candidates[:1] if _is_distinct(route, routes))

    return routes
