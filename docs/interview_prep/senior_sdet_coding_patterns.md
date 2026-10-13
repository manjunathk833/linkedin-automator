# Senior SDET Live Coding Patterns & Algorithmic Scenarios

**Target Level:** Senior SDET / Lead Quality Architect (~6.8 YOE, ₹25–35+ LPA / $50k–$65k USD Band)  
**Languages:** Python & TypeScript  
**Focus:** Concurrency, Data Structures, Resilient API Clients, and Contract Verification Engines  

---

## Pattern 1: Concurrency-Safe Token Bucket Rate Limiter

### Scenario & Problem
You are building an automated API test engine that sends traffic to a downstream microservice with a strict rate limit (e.g., 50 requests/sec with burst capacity of 10). Write a thread-safe token bucket rate limiter to govern request dispatch.

```python
import threading
import time


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill_timestamp = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
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
                # Calculate sleep duration needed for required tokens
                missing = tokens - self.tokens
                sleep_time = min(missing / self.refill_rate, 0.05)
            time.sleep(sleep_time)
        return False
```

---

## Pattern 2: Thread-Safe In-Memory LRU Cache with TTL

### Scenario & Problem
Implement an in-memory cache for API responses or authentication tokens that maintains an eviction policy based on Least Recently Used (LRU) and Time-To-Live (TTL).

```python
from collections import OrderedDict
import threading
import time
from typing import Any


class LRUCacheWithTTL:
    def __init__(self, max_capacity: int, default_ttl_sec: float = 300.0):
        self.max_capacity = max_capacity
        self.default_ttl = default_ttl_sec
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key -> (value, expiry_time)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self.cache:
                return None
            val, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            # Move to end (mark as most recently used)
            self.cache.move_to_end(key)
            return val

    def put(self, key: str, value: Any, ttl_sec: float | None = None) -> None:
        expiry = time.time() + (ttl_sec if ttl_sec is not None else self.default_ttl)
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, expiry)
            # Evict LRU item if capacity exceeded
            if len(self.cache) > self.max_capacity:
                self.cache.popitem(last=False)
```

---

## Pattern 3: Resilient HTTP Client with Exponential Backoff & Jitter

### Scenario & Problem
Implement a resilient API request dispatcher that handles transient HTTP errors (429, 502, 503, 504) using Full Jitter exponential backoff to prevent thundering herd problems.

```python
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


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
        except retryable_exceptions as exc:
            if attempt == max_retries:
                raise exc
            # Full Jitter formula: sleep = uniform(0, min(max_delay, base_delay * 2^attempt))
            ceiling = min(max_delay, base_delay * (2**attempt))
            sleep_duration = random.uniform(0.1, ceiling)
            time.sleep(sleep_duration)
    raise RuntimeError("Retry loop exhausted")
```

---

## Pattern 4: Contract Schema Diff & Validation Engine

### Scenario & Problem
Write a lightweight recursive comparator that diffs an actual JSON API response against an expected contract schema, reporting missing fields, unexpected types, and structural violations.

```python
from typing import Any


def diff_json_contract(expected: Any, actual: Any, path: str = "$") -> list[str]:
    """Recursively validates actual JSON response against expected contract schema.

    Returns a list of detailed divergence descriptions.
    """
    diffs = []

    # 1. Type validation
    if type(expected) is not type(actual) and expected is not None:
        diffs.append(f"Type mismatch at {path}: expected {type(expected).__name__}, got {type(actual).__name__}")
        return diffs

    # 2. Dictionary / Object validation
    if isinstance(expected, dict) and isinstance(actual, dict):
        # Check for missing keys
        for key in expected:
            child_path = f"{path}.{key}"
            if key not in actual:
                diffs.append(f"Missing required key: {child_path}")
            else:
                diffs.extend(diff_json_contract(expected[key], actual[key], child_path))

    # 3. List / Array validation
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) > 0 and len(actual) > 0:
            # Validate first element schema against all actual elements
            template = expected[0]
            for idx, item in enumerate(actual):
                diffs.extend(diff_json_contract(template, item, f"{path}[{idx}]"))

    return diffs
```
