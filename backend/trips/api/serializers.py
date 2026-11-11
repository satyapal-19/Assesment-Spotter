from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

MAX_DAYS_AHEAD = 7
LATE_DEPARTURE_GRACE = timedelta(minutes=15)
MAX_LOAD_LB = 200_000
MAX_PATHS = 3
MAX_POINTS_PER_PATH = 500


def validate_departure(value):
    now = timezone.now()
    if value < now - LATE_DEPARTURE_GRACE:
        raise serializers.ValidationError("Departure time can't be in the past.")
    if value > now + timedelta(days=MAX_DAYS_AHEAD):
        raise serializers.ValidationError(
            f"Departure must be within {MAX_DAYS_AHEAD} days so the forecast covers the trip."
        )
    return value


class TripRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_at = serializers.DateTimeField(validators=[validate_departure])
    load_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)


class HeatmapRequestSerializer(serializers.Serializer):
    departure_at = serializers.DateTimeField(validators=[validate_departure])
    load_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    paths = serializers.ListField(
        min_length=1,
        max_length=MAX_PATHS,
        child=serializers.ListField(
            min_length=1,
            max_length=MAX_POINTS_PER_PATH,
            child=serializers.ListField(
                min_length=2,
                max_length=2,
                child=serializers.FloatField(min_value=-180, max_value=180),
            ),
        ),
    )

    def validate_paths(self, paths):
        if any(abs(lat) > 90 for path in paths for lat, _ in path):
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return paths


def risk_name(risk):
    return None if risk is None else risk.name.lower()


def _round_path(path):
    return [[round(lat, 5), round(lon, 5)] for lat, lon in path]


def _serialize_checkpoint(item):
    checkpoint, weather = item.checkpoint, item.weather
    return {
        "mile": round(checkpoint.mile, 1),
        "lat": round(checkpoint.lat, 5),
        "lon": round(checkpoint.lon, 5),
        "eta": checkpoint.eta,
        "risk": risk_name(item.risk),
        "weather": weather
        and {
            "wind_mph": round(weather.wind_mph, 1),
            "rain_in_hr": round(weather.rain_in_hr, 2),
            "snow_in_hr": round(weather.snow_in_hr, 2),
        },
    }


def _serialize_route(route):
    summary = route["summary"]
    return {
        "id": summary.route_id,
        "duration_s": round(summary.duration_s),
        "distance_miles": round(summary.total_miles, 1),
        "average_risk": None if summary.average_risk is None else round(summary.average_risk, 2),
        "miles_by_risk": {
            "low": round(summary.low_miles, 1),
            "moderate": round(summary.moderate_miles, 1),
            "high": round(summary.high_miles, 1),
            "severe": round(summary.severe_miles, 1),
            "no_travel": round(summary.no_travel_miles, 1),
            "no_data": round(summary.no_data_miles, 1),
        },
        "segments": [
            {"risk": risk_name(segment["risk"]), "path": _round_path(segment["path"])}
            for segment in route["segments"]
        ],
        "checkpoints": [_serialize_checkpoint(item) for item in route["checkpoints"]],
    }


def serialize_plan(plan):
    recommendation = plan["recommendation"]
    return {
        "origin": {
            "name": plan["origin"].name,
            "lat": plan["origin"].lat,
            "lon": plan["origin"].lon,
        },
        "destination": {
            "name": plan["destination"].name,
            "lat": plan["destination"].lat,
            "lon": plan["destination"].lon,
        },
        "departure_at": plan["departure_at"],
        "load_lb": plan["load_lb"],
        "interval_miles": plan["interval_miles"],
        "routes": [_serialize_route(route) for route in plan["routes"]],
        "recommendation": {
            "route_id": recommendation.route_id,
            "is_safe": recommendation.is_safe,
            "is_complete": recommendation.is_complete,
            "reason": recommendation.reason,
        },
    }
