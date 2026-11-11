class TripError(Exception):
    """A planning failure with a message that is safe to show to the driver."""


class PlaceNotFound(TripError):
    pass


class NoRouteFound(TripError):
    pass


class CorridorTooLarge(TripError):
    pass


class UpstreamError(TripError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code
