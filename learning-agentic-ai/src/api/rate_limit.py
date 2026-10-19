"""In-memory, per-IP rate limiting.

Each client IP may make `limit` requests per `window` seconds. The request that exceeds
the limit is rejected with 429 and the IP is blocked for `cooldown` seconds; after the
cooldown its counter starts again from zero.

The client IP is the direct peer address (`request.client.host`); X-Forwarded-For is
not trusted. State is per process, so each worker / replica limits independently.
"""

import math
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.config import RATE_LIMIT_COOLDOWN_SECONDS, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from api.errors import problem_response

EXEMPT_PATHS = frozenset({"/health", "/ready", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})
_PRUNE_THRESHOLD = 10_000


@dataclass
class _Entry:
    window_start: float
    count: int = 0
    blocked_until: float | None = None


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int  # seconds until the window resets (or the block ends)
    retry_after: int | None = None


class RateLimiter:
    def __init__(
        self,
        limit: int = RATE_LIMIT_REQUESTS,
        window: float = RATE_LIMIT_WINDOW_SECONDS,
        cooldown: float = RATE_LIMIT_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window = window
        self.cooldown = cooldown
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)

            if entry and entry.blocked_until is not None and now < entry.blocked_until:
                retry_after = math.ceil(entry.blocked_until - now)
                return RateLimitDecision(False, self.limit, 0, retry_after, retry_after)

            window_over = entry is not None and now - entry.window_start >= self.window
            if entry is None or entry.blocked_until is not None or window_over:
                if len(self._entries) >= _PRUNE_THRESHOLD:
                    self._prune(now)
                entry = self._entries[key] = _Entry(window_start=now)

            entry.count += 1
            if entry.count > self.limit:
                entry.blocked_until = now + self.cooldown
                retry_after = math.ceil(self.cooldown)
                return RateLimitDecision(False, self.limit, 0, retry_after, retry_after)

            reset_after = math.ceil(entry.window_start + self.window - now)
            return RateLimitDecision(True, self.limit, self.limit - entry.count, reset_after)

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, e in self._entries.items()
            if (e.blocked_until is None and now - e.window_start >= self.window)
            or (e.blocked_until is not None and now >= e.blocked_until)
        ]
        for key in expired:
            del self._entries[key]


class RateLimitMiddleware:
    """Applies a RateLimiter to every HTTP request except the exempt paths."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter, exempt_paths: Iterable[str] = EXEMPT_PATHS) -> None:
        self.app = app
        self.limiter = limiter
        self.exempt_paths = frozenset(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        decision = self.limiter.check(client[0] if client else "unknown")
        headers = {
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Reset": str(decision.reset_after),
        }

        if not decision.allowed:
            headers["Retry-After"] = str(decision.retry_after)
            response = problem_response(
                429,
                "RATE_LIMITED",
                f"Rate limit of {self.limiter.limit} requests per {self.limiter.window:g}s exceeded. "
                f"Retry after {decision.retry_after}s.",
                instance=scope["path"],
                request_id=scope.get("state", {}).get("request_id"),
                headers=headers,
                retry_after=decision.retry_after,
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                for name, value in headers.items():
                    response_headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
