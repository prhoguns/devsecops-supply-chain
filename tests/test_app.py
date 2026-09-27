import pytest
from fastapi.testclient import TestClient

from app.main import app, error_rate

client = TestClient(app)


def test_health_endpoints():
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200


def test_work_succeeds_without_injected_errors(monkeypatch):
    monkeypatch.setenv("ERROR_RATE", "0")
    assert all(client.get("/api/work").status_code == 200 for _ in range(50))


def test_work_always_fails_at_full_error_rate(monkeypatch):
    monkeypatch.setenv("ERROR_RATE", "1")
    assert all(client.get("/api/work").status_code == 503 for _ in range(20))


def test_metrics_use_route_templates(monkeypatch):
    monkeypatch.setenv("ERROR_RATE", "0")
    client.get("/api/work")
    client.get("/does-not-exist")
    body = client.get("/metrics").text
    assert 'path="/api/work",status="200"' in body
    assert 'path="unmatched",status="404"' in body
    assert "does-not-exist" not in body


@pytest.mark.parametrize("bad", ["-0.1", "1.5"])
def test_invalid_error_rate_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("ERROR_RATE", bad)
    with pytest.raises(ValueError):
        error_rate()
