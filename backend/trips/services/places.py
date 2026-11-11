import hashlib
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache

from .errors import PlaceNotFound
from .http import get_json

CACHE_SECONDS = 24 * 60 * 60
SUGGESTION_LIMIT = 5


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float

    @property
    def coordinates(self):
        return (self.lat, self.lon)


def _search(endpoint, query, **params):
    return get_json(
        f"{settings.TOMTOM_BASE_URL}/search/2/{endpoint}/{quote(query, safe='')}.json",
        {"key": settings.TOMTOM_API_KEY, **params},
        "The geocoding service",
    ).get("results", [])


def _cache_key(kind, query):
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()
    return f"{kind}:{digest}"


def geocode(query):
    key = _cache_key("place", query)
    place = cache.get(key)
    if place:
        return place

    results = _search("geocode", query, limit=1)
    if not results:
        raise PlaceNotFound(f'Could not find "{query}". Try adding the state or country.')

    result = results[0]
    place = Place(
        name=result["address"]["freeformAddress"],
        lat=result["position"]["lat"],
        lon=result["position"]["lon"],
    )
    cache.set(key, place, CACHE_SECONDS)
    return place


def suggest(query):
    # Search has a much smaller free allowance than geocoding, and people retype the same names.
    key = _cache_key("suggest", query)
    suggestions = cache.get(key)
    if suggestions is not None:
        return suggestions

    results = _search("search", query, typeahead="true", idxSet="Geo", limit=SUGGESTION_LIMIT)
    suggestions = list(dict.fromkeys(item["address"]["freeformAddress"] for item in results))
    cache.set(key, suggestions, CACHE_SECONDS)
    return suggestions
