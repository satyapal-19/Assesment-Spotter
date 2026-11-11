from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from trips.services.errors import CorridorTooLarge, NoRouteFound, PlaceNotFound, TripError

REQUEST_ERRORS = (PlaceNotFound, NoRouteFound, CorridorTooLarge)


def exception_handler(exc, context):
    if isinstance(exc, TripError):
        status = 422 if isinstance(exc, REQUEST_ERRORS) else 502
        return Response({"detail": str(exc)}, status=status)
    return drf_exception_handler(exc, context)
