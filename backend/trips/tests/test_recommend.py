import pytest

from trips.services.recommend import RouteSummary, recommend, summarize
from trips.services.risk import Risk


def summary(route_id, duration=3600, **miles):
    return RouteSummary(
        route_id=route_id,
        duration_s=duration,
        no_travel_miles=miles.get("no_travel", 0),
        no_data_miles=miles.get("no_data", 0),
        severe_miles=miles.get("severe", 0),
        high_miles=miles.get("high", 0),
        moderate_miles=miles.get("moderate", 0),
        low_miles=miles.get("low", 0),
        average_risk=miles.get("average", 0),
    )


def test_miles_are_split_halfway_between_checkpoints():
    result = summarize(
        "a",
        [(0, Risk.LOW), (10, Risk.HIGH), (20, Risk.SEVERE)],
        duration_s=1000,
    )
    assert result.low_miles == pytest.approx(5)
    assert result.high_miles == pytest.approx(10)
    assert result.severe_miles == pytest.approx(5)


def test_miles_add_up_to_route_length_with_a_short_last_segment():
    points = [(0, Risk.LOW), (25, Risk.MODERATE), (50, Risk.HIGH), (57.3, Risk.LOW)]
    result = summarize("a", points, duration_s=1000)
    assert result.total_miles == pytest.approx(57.3)


def test_average_risk_is_weighted_by_distance():
    result = summarize("a", [(0, Risk.LOW), (10, Risk.SEVERE)], duration_s=1000)
    assert result.average_risk == pytest.approx(1.5)

    uneven = summarize(
        "b",
        [(0, Risk.LOW), (10, Risk.LOW), (20, Risk.SEVERE)],
        duration_s=1000,
    )
    assert uneven.average_risk == pytest.approx(0.75)


def test_missing_weather_is_not_counted_as_low():
    result = summarize("a", [(0, Risk.LOW), (10, None)], duration_s=1000)
    assert result.low_miles == pytest.approx(5)
    assert result.no_data_miles == pytest.approx(5)
    assert result.average_risk == pytest.approx(0)


def test_route_with_no_known_weather_has_no_average():
    result = summarize("a", [(0, None), (10, None)], duration_s=1000)
    assert result.average_risk is None


def test_fewest_severe_miles_wins_first():
    worse = summary("worse", severe=5, high=0, average=0, duration=100)
    better = summary("better", severe=1, high=50, average=3, duration=900)
    assert recommend([worse, better]).route_id == "better"


def test_high_miles_break_a_severe_tie():
    worse = summary("worse", severe=1, high=9, average=0, duration=100)
    better = summary("better", severe=1, high=2, average=3, duration=900)
    assert recommend([worse, better]).route_id == "better"


def test_average_risk_breaks_a_high_tie():
    worse = summary("worse", high=2, average=1.2, duration=100)
    better = summary("better", high=2, average=0.8, duration=900)
    assert recommend([worse, better]).route_id == "better"


def test_travel_time_is_the_last_tie_break():
    slower = summary("slower", high=2, average=0.8, duration=900)
    faster = summary("faster", high=2, average=0.8, duration=100)
    assert recommend([slower, faster]).route_id == "faster"


def test_rounding_noise_does_not_decide_a_comparison():
    slower = summary("slower", severe=1.0001, average=1.001, duration=900)
    faster = summary("faster", severe=1.0002, average=1.002, duration=100)
    assert recommend([slower, faster]).route_id == "faster"


def test_no_travel_outranks_severe():
    blocked = summary("blocked", no_travel=1)
    rough = summary("rough", severe=200, high=100, average=3)
    result = recommend([blocked, rough])
    assert result.route_id == "rough"
    assert result.is_safe is True


def test_all_routes_blocked_gives_the_least_bad_with_a_warning():
    a = summary("a", no_travel=30)
    b = summary("b", no_travel=5)
    result = recommend([a, b])
    assert result.route_id == "b"
    assert result.is_safe is False
    assert "No Travel" in result.reason


def test_unknown_weather_ranks_below_known_severe():
    unknown = summary("unknown", no_data=20)
    rough = summary("rough", severe=20, average=3)
    assert recommend([unknown, rough]).route_id == "rough"


def test_reason_names_the_deciding_criterion():
    a = summary("a", severe=4)
    b = summary("b", severe=1)
    assert "Severe" in recommend([a, b]).reason

    c = summary("c", average=1, duration=100)
    d = summary("d", average=1, duration=900)
    assert "travel time" in recommend([c, d]).reason


def test_recommendation_is_complete_when_the_forecast_covers_the_route():
    assert recommend([summary("a"), summary("b", severe=2)]).is_complete is True


def test_recommended_route_with_forecast_gaps_is_flagged():
    a = summary("a", no_data=40)
    b = summary("b", no_data=12.5)
    result = recommend([a, b])
    assert result.route_id == "b"
    assert result.is_safe is True
    assert result.is_complete is False
    assert "12.5 miles" in result.reason


def test_reason_names_what_beat_each_route():
    winner = summary("C", average=0, duration=900)
    riskier_but_faster = summary("A", average=0.5, duration=100)
    slower = summary("B", average=0, duration=1000)
    reason = recommend([riskier_but_faster, winner, slower]).reason
    assert "a lower average risk than Route A" in reason
    assert "a shorter travel time than Route B" in reason


def test_reason_groups_routes_beaten_the_same_way():
    reason = recommend([summary("A"), summary("B", severe=4), summary("C", severe=2)]).reason
    assert reason == "This route has fewer Severe miles than Route B and C."
