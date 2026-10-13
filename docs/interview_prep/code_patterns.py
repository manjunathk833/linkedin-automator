"""
Executable Python Reference Implementations for Senior SDET Live Coding Patterns.
Encompasses:
1. TokenBucketRateLimiter
2. LRUCacheWithTTL
3. execute_with_exponential_backoff
4. diff_json_contract
"""

from __future__ import annotations

import random
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TokenBucketRateLimiter:
    """Thread-safe Token Bucket Rate Limiter with burst capacity and time refill."""

    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill_timestamp = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill_timestamp
        tokens_to_add = elapsed * self.refill_rate
        if tokens_to_add > 0:
            self.tokens = min(float(self.capacity), self.tokens + tokens_to_add)
            self.last_refill_timestamp = now

    def acquire(self, tokens: int = 1, timeout_sec: float = 5.0) -> bool:
        """Attempts to acquire tokens within timeout_sec. Returns True if granted, False if timed out."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                missing = tokens - self.tokens
                sleep_time = min(missing / self.refill_rate, 0.05)
            time.sleep(sleep_time)
        return False


class LRUCacheWithTTL:
    """Thread-safe In-Memory LRU Cache with Time-to-Live (TTL) expiration."""

    def __init__(self, max_capacity: int, default_ttl_sec: float = 300.0):
        self.max_capacity = max_capacity
        self.default_ttl = default_ttl_sec
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self.cache:
                return None
            val, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return val

    def put(self, key: str, value: Any, ttl_sec: float | None = None) -> None:
        expiry = time.time() + (ttl_sec if ttl_sec is not None else self.default_ttl)
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, expiry)
            if len(self.cache) > self.max_capacity:
                self.cache.popitem(last=False)


def execute_with_exponential_backoff(
    action: Callable[[], T],
    max_retries: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retryable_exceptions: tuple = (Exception,),
) -> T:
    """Executes action with exponential backoff and randomized Full Jitter."""
    for attempt in range(max_retries + 1):
        try:
            return action()
        except retryable_exceptions:
            if attempt == max_retries:
                raise
            ceiling = min(max_delay, base_delay * (2**attempt))
            sleep_duration = random.uniform(0.1, ceiling)
            time.sleep(sleep_duration)
    raise RuntimeError("Retry loop exhausted")


def diff_json_contract(expected: Any, actual: Any, path: str = "$") -> list[str]:
    """Recursively validates actual JSON response against expected contract schema.

    Returns a list of divergence descriptions.
    """
    diffs = []

    # 1. Type validation
    if type(expected) is not type(actual) and expected is not None:
        diffs.append(f"Type mismatch at {path}: expected {type(expected).__name__}, got {type(actual).__name__}")
        return diffs

    # 2. Dictionary / Object validation
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in expected:
            child_path = f"{path}.{key}"
            if key not in actual:
                diffs.append(f"Missing required key: {child_path}")
            else:
                diffs.extend(diff_json_contract(expected[key], actual[key], child_path))

    # 3. List / Array validation
    elif isinstance(expected, list) and isinstance(actual, list) and len(expected) > 0 and len(actual) > 0:
        template = expected[0]
        for idx, item in enumerate(actual):
            diffs.extend(diff_json_contract(template, item, f"{path}[{idx}]"))

    return diffs
