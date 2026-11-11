from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from trips.services.heatmap import build_heatmap
from trips.services.places import suggest
from trips.services.planner import plan_trip

from .serializers import HeatmapRequestSerializer, TripRequestSerializer, serialize_plan
from .throttles import PlacesThrottle, TripThrottle

MIN_SUGGEST_LENGTH = 3


@api_view(["POST"])
@throttle_classes([TripThrottle])
def plan(request):
    serializer = TripRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    result = plan_trip(
        origin=data["origin"],
        destination=data["destination"],
        departure=data["departure_at"],
        load_lb=data["load_lb"],
        interval_miles=data["interval_miles"],
    )
    return Response(serialize_plan(result))


@api_view(["POST"])
@throttle_classes([TripThrottle])
def heatmap(request):
    serializer = HeatmapRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return Response(build_heatmap(data["paths"], data["departure_at"], data["load_lb"]))


@api_view(["GET"])
@throttle_classes([PlacesThrottle])
def places(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < MIN_SUGGEST_LENGTH:
        return Response({"suggestions": []})
    return Response({"suggestions": suggest(query)})
