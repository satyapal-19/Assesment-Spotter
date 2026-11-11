import logging

import pytest
import requests

from trips.services import http
from trips.services.errors import UpstreamError

URL = "https://example.test/routes"
PARAMS = {"key": "secret-key"}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.payload = payload

    def json(self):
        if self.payload is None:
            raise ValueError("no JSON")
        return self.payload


def respond_with(monkeypatch, response):
    monkeypatch.setattr(http._session, "get", lambda *args, **kwargs: response)


def test_successful_response_is_returned(monkeypatch):
    respond_with(monkeypatch, FakeResponse(payload={"routes": []}))
    assert http.get_json(URL, PARAMS, "The routing service") == {"routes": []}


def test_rejected_request_logs_the_status(monkeypatch, caplog):
    respond_with(monkeypatch, FakeResponse(status_code=401))
    with caplog.at_level(logging.WARNING), pytest.raises(UpstreamError, match="unavailable"):
        http.get_json(URL, PARAMS, "The routing service")
    assert "HTTP 401" in caplog.text


def test_request_limit_gets_its_own_message(monkeypatch):
    respond_with(monkeypatch, FakeResponse(status_code=429))
    with pytest.raises(UpstreamError, match="request limit"):
        http.get_json(URL, PARAMS, "The weather service")


def test_connection_failure_does_not_log_the_api_key(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise requests.ConnectionError(f"failed: {URL}?key=secret-key")

    monkeypatch.setattr(http._session, "get", fail)
    with caplog.at_level(logging.WARNING), pytest.raises(UpstreamError) as error:
        http.get_json(URL, PARAMS, "The routing service")
    assert "ConnectionError" in caplog.text
    assert "secret-key" not in caplog.text
    assert "secret-key" not in str(error.value)


def test_invalid_json_is_an_upstream_error(monkeypatch):
    respond_with(monkeypatch, FakeResponse())
    with pytest.raises(UpstreamError):
        http.get_json(URL, PARAMS, "The weather service")


def test_rejected_request_carries_its_status(monkeypatch):
    respond_with(monkeypatch, FakeResponse(status_code=400))
    with pytest.raises(UpstreamError) as error:
        http.get_json(URL, PARAMS, "The routing service")
    assert error.value.status_code == 400
