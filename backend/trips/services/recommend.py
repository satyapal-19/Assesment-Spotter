import math
from dataclasses import dataclass

from .risk import Risk


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    duration_s: float
    no_travel_miles: float
    no_data_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    average_risk: float | None

    @property
    def total_miles(self):
        return (
            self.no_travel_miles
            + self.no_data_miles
            + self.severe_miles
            + self.high_miles
            + self.moderate_miles
            + self.low_miles
        )


@dataclass(frozen=True)
class Recommendation:
    route_id: str
    is_safe: bool
    is_complete: bool
    reason: str


def summarize(route_id, points, duration_s):
    """Build a summary from (mile, risk) pairs ordered along the route.

    Each checkpoint owns the distance halfway to its neighbours. A risk of None
    means no forecast covers that checkpoint's arrival time.
    """
    miles = {level: 0.0 for level in [*Risk, None]}
    for index, (mile, risk) in enumerate(points):
        start = (points[index - 1][0] + mile) / 2 if index > 0 else mile
        end = (mile + points[index + 1][0]) / 2 if index < len(points) - 1 else mile
        miles[risk] += end - start

    known_miles = sum(length for level, length in miles.items() if level is not None)
    weighted = sum(level * length for level, length in miles.items() if level is not None)

    return RouteSummary(
        route_id=route_id,
        duration_s=duration_s,
        no_travel_miles=miles[Risk.NO_TRAVEL],
        no_data_miles=miles[None],
        severe_miles=miles[Risk.SEVERE],
        high_miles=miles[Risk.HIGH],
        moderate_miles=miles[Risk.MODERATE],
        low_miles=miles[Risk.LOW],
        average_risk=weighted / known_miles if known_miles else None,
    )


def _average(route):
    return math.inf if route.average_risk is None else round(route.average_risk, 2)


# Values are rounded so that floating point noise can't decide a comparison. No Travel and
# unknown weather aren't in the published order, but both have to rank above Severe:
# a route shouldn't win just because its danger falls outside the Severe count.
_CRITERIA = (
    ("fewer No Travel miles", lambda r: round(r.no_travel_miles, 1)),
    ("fewer miles without forecast data", lambda r: round(r.no_data_miles, 1)),
    ("fewer Severe miles", lambda r: round(r.severe_miles, 1)),
    ("fewer High miles", lambda r: round(r.high_miles, 1)),
    ("a lower average risk", _average),
    ("a shorter travel time", lambda r: round(r.duration_s)),
)


def _rank(route):
    return tuple(value(route) for _, value in _CRITERIA)


def _deciding_label(winner, other):
    for label, value in _CRITERIA:
        if value(winner) != value(other):
            return label
    return None


def _explain(winner, others):
    """Say what beat each other route, which can be a different criterion for each one."""
    if not others:
        return "This is the only route available."

    beaten = {}
    for other in others:
        label = _deciding_label(winner, other)
        if label:
            beaten.setdefault(label, []).append(other.route_id)
    if not beaten:
        return "All routes are tied on risk and travel time."

    parts = [
        f"{label} than Route {' and '.join(sorted(route_ids))}"
        for label, _ in _CRITERIA
        if (route_ids := beaten.get(label))
    ]
    return f"This route has {' and '.join(parts)}."


def recommend(summaries):
    ranked = sorted(summaries, key=_rank)
    winner, others = ranked[0], ranked[1:]

    # False when part of the recommended route is beyond the forecast, so its weather is unknown.
    is_complete = round(winner.no_data_miles, 1) == 0

    if winner.no_travel_miles > 0:
        return Recommendation(
            route_id=winner.route_id,
            is_safe=False,
            is_complete=is_complete,
            reason=(
                "Every route crosses No Travel weather. This one has the least, "
                f"at {winner.no_travel_miles:.1f} miles. Consider a different departure time."
            ),
        )

    reason = _explain(winner, others)
    if not is_complete:
        reason += (
            f" The forecast doesn't reach {winner.no_data_miles:.1f} miles of it yet,"
            " so check again closer to departure."
        )
    return Recommendation(
        route_id=winner.route_id,
        is_safe=True,
        is_complete=is_complete,
        reason=reason,
    )
