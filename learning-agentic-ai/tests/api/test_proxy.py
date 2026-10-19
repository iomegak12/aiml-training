"""Running behind nginx: root path, trusted X-Forwarded-For, and the new settings."""

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api import create_app
from api import config as api_config
from api.config import ApiConfigurationError, ApiSettings
from api.rate_limit import RateLimiter


@pytest.fixture
def isolated_api_env(monkeypatch):
    monkeypatch.setattr(api_config, "load_dotenv", lambda *args, **kwargs: None)
    for name in ("API_HOST", "API_PORT", "LOG_DIR", "LOG_LEVEL", "API_ROOT_PATH", "FORWARDED_ALLOW_IPS", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_proxy_settings_defaults(isolated_api_env):
    settings = ApiSettings.from_env()
    assert settings.root_path == ""
    assert settings.forwarded_allow_ips == "127.0.0.1"
    assert settings.public_base_url is None


def test_proxy_settings_from_env(isolated_api_env, monkeypatch):
    monkeypatch.setenv("API_ROOT_PATH", "/api/")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost/api/")
    settings = ApiSettings.from_env()
    assert settings.root_path == "/api"
    assert settings.forwarded_allow_ips == "*"
    assert settings.public_base_url == "http://localhost/api"


def test_root_path_must_start_with_slash(isolated_api_env, monkeypatch):
    monkeypatch.setenv("API_ROOT_PATH", "api")
    with pytest.raises(ApiConfigurationError):
        ApiSettings.from_env()


def _client(log_dir, runtime, *, root_path="", trusted=None, limiter=None) -> TestClient:
    app = create_app(
        settings=ApiSettings(log_dir=log_dir, root_path=root_path),
        runtime=runtime,
        rate_limiter=limiter,
        show_banner=False,
    )
    if trusted is not None:
        app = ProxyHeadersMiddleware(app, trusted_hosts=trusted)  # what uvicorn applies with proxy_headers=True
    return TestClient(app)


def test_root_path_routes_docs_and_exemptions(log_dir, make_runtime):
    # nginx strips /api, so requests arrive as /health, /chat, ...
    limiter = RateLimiter(limit=0, window=60, cooldown=30)
    with _client(log_dir, make_runtime(), root_path="/api", limiter=limiter) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200  # still exempt while every other path is blocked
        assert client.post("/chat", json={"message": "hi"}).status_code == 429
        assert "/api/openapi.json" in client.get("/docs").text
        assert client.get("/openapi.json").json()["servers"] == [{"url": "/api"}]


def test_trusted_proxy_client_ip_used_for_logs_and_limits(log_dir, make_runtime, read_logs):
    limiter = RateLimiter(limit=1, window=60, cooldown=30)
    with _client(log_dir, make_runtime(), trusted="*", limiter=limiter) as client:
        first = client.get("/openapi.json")  # exempt; just logs
        a1 = client.post("/chat", json={}, headers={"X-Forwarded-For": "203.0.113.7"})
        a2 = client.post("/chat", json={}, headers={"X-Forwarded-For": "203.0.113.7"})
        b1 = client.post("/chat", json={}, headers={"X-Forwarded-For": "198.51.100.9"})

    assert first.status_code == 200
    assert a1.status_code == 422  # allowed (validation error), counted for 203.0.113.7
    assert a2.status_code == 429  # same client over the limit
    assert b1.status_code == 422  # a different client has its own limit
    ips = [e["client_ip"] for e in read_logs() if e.get("path") == "/chat"]
    assert ips == ["203.0.113.7", "203.0.113.7", "198.51.100.9"]


def test_untrusted_proxy_header_is_ignored(log_dir, make_runtime, read_logs):
    with _client(log_dir, make_runtime(), trusted="127.0.0.1") as client:
        client.get("/health", headers={"X-Forwarded-For": "203.0.113.7"})

    entry = next(e for e in read_logs() if e.get("path") == "/health")
    assert entry["client_ip"] == "testclient"
