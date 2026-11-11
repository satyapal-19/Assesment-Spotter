import pytest

from trips.services.risk import Risk, Weather, classify

LIGHT_LOAD = 20_000


def wind(mph, load=LIGHT_LOAD):
    return classify(Weather(wind_mph=mph, rain_in_hr=0, snow_in_hr=0), load)


def rain(in_hr):
    return classify(Weather(wind_mph=0, rain_in_hr=in_hr, snow_in_hr=0), LIGHT_LOAD)


def snow(in_hr):
    return classify(Weather(wind_mph=0, rain_in_hr=0, snow_in_hr=in_hr), LIGHT_LOAD)


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, Risk.LOW),
        (24.9, Risk.LOW),
        (25, Risk.MODERATE),
        (34.5, Risk.MODERATE),
        (35, Risk.HIGH),
        (44.9, Risk.HIGH),
        (45, Risk.SEVERE),
        (54.9, Risk.SEVERE),
        (55, Risk.NO_TRAVEL),
        (80, Risk.NO_TRAVEL),
    ],
)
def test_wind_bands(mph, expected):
    assert wind(mph) == expected


@pytest.mark.parametrize(
    "in_hr, expected",
    [
        (0, Risk.LOW),
        (0.09, Risk.LOW),
        (0.10, Risk.MODERATE),
        (0.24, Risk.MODERATE),
        (0.25, Risk.HIGH),
        (0.49, Risk.HIGH),
        (0.50, Risk.SEVERE),
        (1.00, Risk.SEVERE),
        (1.01, Risk.NO_TRAVEL),
    ],
)
def test_rain_bands(in_hr, expected):
    assert rain(in_hr) == expected


@pytest.mark.parametrize(
    "in_hr, expected",
    [
        (0, Risk.LOW),
        (0.49, Risk.LOW),
        (0.5, Risk.MODERATE),
        (0.99, Risk.MODERATE),
        (1.0, Risk.HIGH),
        (1.99, Risk.HIGH),
        (2.0, Risk.SEVERE),
        (3.0, Risk.SEVERE),
        (3.01, Risk.NO_TRAVEL),
    ],
)
def test_snow_bands(in_hr, expected):
    assert snow(in_hr) == expected


@pytest.mark.parametrize(
    "mph, load, expected",
    [
        (55, 1_000, Risk.NO_TRAVEL),
        (45, 30_000, Risk.SEVERE),
        (45, 30_001, Risk.NO_TRAVEL),
        (54.9, 30_001, Risk.NO_TRAVEL),
        (35, 40_000, Risk.HIGH),
        (35, 40_001, Risk.SEVERE),
        (44.9, 40_001, Risk.SEVERE),
        (34.9, 80_000, Risk.MODERATE),
    ],
)
def test_load_rules(mph, load, expected):
    assert wind(mph, load) == expected


def test_worst_condition_wins():
    weather = Weather(wind_mph=26, rain_in_hr=0.3, snow_in_hr=2.5)
    assert classify(weather, LIGHT_LOAD) == Risk.SEVERE


def test_load_rule_cannot_lower_risk_from_other_conditions():
    weather = Weather(wind_mph=36, rain_in_hr=1.5, snow_in_hr=0)
    assert classify(weather, 50_000) == Risk.NO_TRAVEL
