import pytest
from langchain_core.messages import AIMessage

from api.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def test_limit_window_and_cooldown(clock):
    limiter = RateLimiter(limit=100, window=60, cooldown=30, clock=clock)

    decisions = [limiter.check("1.2.3.4") for _ in range(100)]
    assert all(d.allowed for d in decisions)
    assert decisions[-1].remaining == 0

    blocked = limiter.check("1.2.3.4")  # 101st request
    assert not blocked.allowed
    assert blocked.retry_after == 30

    clock.now += 29
    assert limiter.check("1.2.3.4").retry_after == 1  # still blocked

    clock.now += 1  # cooldown over: counter starts from zero
    after = limiter.check("1.2.3.4")
    assert after.allowed
    assert after.remaining == 99


def test_window_resets_after_a_minute(clock):
    limiter = RateLimiter(limit=2, window=60, cooldown=30, clock=clock)
    assert limiter.check("ip").allowed and limiter.check("ip").allowed

    clock.now += 60
    decision = limiter.check("ip")
    assert decision.allowed
    assert decision.remaining == 1


def test_limits_are_per_ip(clock):
    limiter = RateLimiter(limit=1, window=60, cooldown=30, clock=clock)
    assert limiter.check("a").allowed
    assert not limiter.check("a").allowed
    assert limiter.check("b").allowed


def test_middleware_returns_429_problem(make_client, make_runtime, clock):
    runtime = make_runtime(chat=[AIMessage(content=str(i)) for i in range(3)])
    client = make_client(runtime, rate_limiter=RateLimiter(limit=2, window=60, cooldown=30, clock=clock))

    assert client.post("/chat", json={"message": "1"}).status_code == 200
    assert client.post("/chat", json={"message": "2"}).status_code == 200
    response = client.post("/chat", json={"message": "3"})

    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["Retry-After"] == "30"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    body = response.json()
    assert body["code"] == "RATE_LIMITED"
    assert body["retry_after"] == 30
    assert body["request_id"] == response.headers["X-Request-ID"]

    # Probes and docs are never limited, even while blocked.
    for path in ("/health", "/ready", "/docs", "/openapi.json"):
        assert client.get(path).status_code in (200, 503)

    clock.now += 30
    assert client.post("/chat", json={"message": "again"}).status_code == 200


def test_rate_limited_requests_are_logged(make_client, make_runtime, clock, read_logs):
    client = make_client(make_runtime(), rate_limiter=RateLimiter(limit=0, window=60, cooldown=30, clock=clock))

    client.post("/chat", json={"message": "hi"})

    entry = next(e for e in read_logs() if e.get("path") == "/chat")
    assert entry["status"] == 429
