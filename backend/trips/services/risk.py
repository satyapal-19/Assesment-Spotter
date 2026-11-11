from dataclasses import dataclass
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


def wind_risk(mph, load_lb):
    if mph >= 55:
        return Risk.NO_TRAVEL
    if mph >= 45:
        return Risk.NO_TRAVEL if load_lb > 30_000 else Risk.SEVERE
    if mph >= 35:
        return Risk.SEVERE if load_lb > 40_000 else Risk.HIGH
    if mph >= 25:
        return Risk.MODERATE
    return Risk.LOW


# The published bands share their edges (0.25 in/hr is both Moderate and High).
# An edge value takes the higher band, except at the top, where No Travel is strictly greater.
def rain_risk(in_hr):
    if in_hr > 1.0:
        return Risk.NO_TRAVEL
    if in_hr >= 0.5:
        return Risk.SEVERE
    if in_hr >= 0.25:
        return Risk.HIGH
    if in_hr >= 0.1:
        return Risk.MODERATE
    return Risk.LOW


def snow_risk(in_hr):
    if in_hr > 3.0:
        return Risk.NO_TRAVEL
    if in_hr >= 2.0:
        return Risk.SEVERE
    if in_hr >= 1.0:
        return Risk.HIGH
    if in_hr >= 0.5:
        return Risk.MODERATE
    return Risk.LOW


def classify(weather, load_lb):
    return max(
        wind_risk(weather.wind_mph, load_lb),
        rain_risk(weather.rain_in_hr),
        snow_risk(weather.snow_in_hr),
    )
