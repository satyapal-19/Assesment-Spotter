import math
from datetime import timedelta

from .errors import CorridorTooLarge
from .geo import distance_miles
from .risk import classify
from .weather import get_forecasts, weather_at

HOURS = 48
CORRIDOR_MILES = 50
MILES_PER_DEGREE_LAT = 69.0
MAX_POINTS = 300
MIN_STEP_MILES = 10
MAX_STEP_MILES = 60


def _path_miles(path):
    return sum(distance_miles(a, b) for a, b in zip(path, path[1:]))


def _grid_step_miles(paths):
    # A corridor around the longest path covers roughly length x width. Picking the step from that
    # area keeps the point count, and with it the rendering cost, about the same for any trip.
    longest = max(_path_miles(path) for path in paths)
    area = (longest + 2 * CORRIDOR_MILES) * 2 * CORRIDOR_MILES
    return min(max(math.sqrt(area / MAX_POINTS), MIN_STEP_MILES), MAX_STEP_MILES)


def corridor_cells(paths, step_miles):
    """Return the regular lat/lon grid cells within the corridor around any path."""
    mid_lat = sum(lat for path in paths for lat, _ in path) / sum(len(path) for path in paths)
    lat_step = step_miles / MILES_PER_DEGREE_LAT
    lon_step = lat_step / max(math.cos(math.radians(mid_lat)), 0.1)
    reach = math.ceil(CORRIDOR_MILES / step_miles) + 1

    cells = {}
    for path in paths:
        for lat, lon in path:
            row = round(lat / lat_step)
            column = round(lon / lon_step)
            for r in range(row - reach, row + reach + 1):
                for c in range(column - reach, column + reach + 1):
                    if (r, c) in cells:
                        continue
                    cell = (r * lat_step, c * lon_step)
                    if distance_miles((lat, lon), cell) <= CORRIDOR_MILES:
                        cells[(r, c)] = cell
    return list(cells.values())


def corridor_grid(paths):
    step_miles = _grid_step_miles(paths)
    cells = corridor_cells(paths, step_miles)
    # Routes that split apart cover more ground than one corridor, so widen the spacing to match.
    if len(cells) > MAX_POINTS and step_miles < MAX_STEP_MILES:
        step_miles = min(step_miles * math.sqrt(len(cells) / MAX_POINTS), MAX_STEP_MILES)
        cells = corridor_cells(paths, step_miles)
    # Real trips stay close to the target. Far more cells means the paths are not routes.
    if len(cells) > 2 * MAX_POINTS:
        raise CorridorTooLarge("This trip covers too large an area for the weather heatmap.")
    return step_miles, cells


def build_heatmap(paths, departure, load_lb):
    step_miles, cells = corridor_grid(paths)
    forecasts = get_forecasts(cells)

    points = []
    for lat, lon in cells:
        levels = []
        for hour in range(HOURS + 1):
            weather = weather_at(forecasts, lat, lon, departure + timedelta(hours=hour))
            levels.append(None if weather is None else int(classify(weather, load_lb)))
        points.append({"lat": round(lat, 4), "lon": round(lon, 4), "risk": levels})

    return {
        "departure_at": departure,
        "hours": HOURS,
        "step_miles": round(step_miles, 1),
        "points": points,
    }
