from rest_framework.throttling import AnonRateThrottle


class TripThrottle(AnonRateThrottle):
    scope = "trips"


class PlacesThrottle(AnonRateThrottle):
    scope = "places"
