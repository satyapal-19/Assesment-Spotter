import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .errors import UpstreamError

logger = logging.getLogger(__name__)

# Connecting gets its own short limit. On a network where IPv6 is advertised but does not
# work, each attempt would otherwise wait out the full read timeout before trying IPv4.
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 20
TOO_MANY_REQUESTS = 429

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(
        pool_maxsize=8,
        max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[502, 503, 504]),
    ),
)


def get_json(url, params, service_name):
    unavailable = UpstreamError(f"{service_name} is unavailable. Please try again.")

    try:
        response = _session.get(
            url, params=params, timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
        )
    except requests.RequestException as exc:
        # The exception text can contain the URL and its API key, so only the type is logged.
        logger.warning("%s request failed: %s", service_name, type(exc).__name__)
        raise unavailable from exc

    if response.status_code == TOO_MANY_REQUESTS:
        logger.warning("%s request limit reached", service_name)
        raise UpstreamError(
            f"{service_name} has reached its request limit. Please try again in a few minutes."
        )
    if not response.ok:
        logger.warning("%s returned HTTP %s", service_name, response.status_code)
        unavailable.status_code = response.status_code
        raise unavailable

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("%s returned a response that is not JSON", service_name)
        raise unavailable from exc
