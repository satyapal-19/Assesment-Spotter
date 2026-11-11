from bisect import bisect_right
from dataclasses import dataclass
from datetime import timedelta

from .geo import lerp_point


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    lat: float
    lon: float
    eta: object


def position_at(route, mile):
    """Return the (point, elapsed seconds) reached after driving `mile` miles along the route."""
    index = min(bisect_right(route.miles, mile), len(route.miles) - 1)
    start, end = route.miles[index - 1], route.miles[index]
    fraction = (mile - start) / (end - start) if end > start else 0.0
    point = lerp_point(route.points[index - 1], route.points[index], fraction)
    seconds = (
        route.seconds[index - 1] + (route.seconds[index] - route.seconds[index - 1]) * fraction
    )
    return point, seconds


def checkpoint_miles(total_miles, interval_miles):
    miles = []
    mile = 0.0
    while mile < total_miles:
        miles.append(mile)
        mile += interval_miles
    miles.append(total_miles)
    return miles


def sample_checkpoints(route, interval_miles, departure):
    checkpoints = []
    for mile in checkpoint_miles(route.miles[-1], interval_miles):
        (lat, lon), seconds = position_at(route, mile)
        checkpoints.append(
            Checkpoint(mile=mile, lat=lat, lon=lon, eta=departure + timedelta(seconds=seconds))
        )
    return checkpoints


def thin_route(route, spacing_miles):
    """Drop points closer than `spacing_miles` to the last kept one, keeping both ends.

    Kept points carry their original mile and time values, so positions along the thinned
    route still line up with the checkpoints.
    """
    keep = [0]
    for index in range(1, len(route.miles) - 1):
        if route.miles[index] - route.miles[keep[-1]] >= spacing_miles:
            keep.append(index)
    keep.append(len(route.miles) - 1)
    return type(route)(
        points=[route.points[i] for i in keep],
        miles=[route.miles[i] for i in keep],
        seconds=[route.seconds[i] for i in keep],
    )


def path_between(route, start_mile, end_mile):
    """Return the part of the route between two miles, cut exactly at both ends."""
    first = bisect_right(route.miles, start_mile)
    last = bisect_right(route.miles, end_mile)
    return [
        position_at(route, start_mile)[0],
        *route.points[first:last],
        position_at(route, end_mile)[0],
    ]
