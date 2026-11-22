from __future__ import annotations

import pytest

from src.security.rate_limit import LoginThrottle, TokenBucketLimiter


def test_token_bucket_limiter_allow():
    limiter = TokenBucketLimiter(capacity=2, rate_per_sec=1.0)
    
    now = 1000.0
    # Burst capacity 2
    assert limiter.allow("user1", now=now) is True
    assert limiter.allow("user1", now=now) is True
    assert limiter.allow("user1", now=now) is False
    
    # Advance time by 0.5s -> 0.5 tokens added, total 0.5 -> not enough for cost 1.0
    now = 1000.5
    assert limiter.allow("user1", now=now) is False
    
    # Advance time to 1.0s -> 1.0 token added -> allows 1 request
    now = 1001.0
    assert limiter.allow("user1", now=now) is True
    assert limiter.allow("user1", now=now) is False

def test_token_bucket_limiter_eviction():
    limiter = TokenBucketLimiter(capacity=1, rate_per_sec=1.0, max_keys=2)
    
    limiter.allow("user1", now=1000.0)
    limiter.allow("user2", now=1000.0)
    
    # Third key should trigger eviction
    limiter.allow("user3", now=1000.0)
    
    # Wait, because none of them are full (rate=1, so it takes 1s to fill),
    # the eviction logic drops the oldest updated one.
    assert len(limiter._buckets) <= 2
    assert "user3" in limiter._buckets

def test_token_bucket_invalid_params():
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=0)
    with pytest.raises(ValueError):
        TokenBucketLimiter(rate_per_sec=0)

def test_login_throttle():
    throttle = LoginThrottle(max_failures=3, base_lock_sec=5.0, max_lock_sec=60.0)
    now = 1000.0
    
    # 1st failure
    assert throttle.failure("ip1", now=now) == 0.0
    assert throttle.remaining("ip1", now=now) == 0.0
    
    # 2nd failure
    assert throttle.failure("ip1", now=now) == 0.0
    
    # 3rd failure - triggers lockout (base_lock_sec * 2^0 = 5.0)
    lock = throttle.failure("ip1", now=now)
    assert lock == 5.0
    assert throttle.remaining("ip1", now=now) == 5.0
    
    # Advance time within lock
    now = 1002.0
    assert throttle.remaining("ip1", now=now) == 3.0
    
    # 4th failure - extends lockout (base_lock_sec * 2^1 = 10.0)
    lock = throttle.failure("ip1", now=now)
    assert lock == 10.0
    assert throttle.remaining("ip1", now=now) == 10.0
    
    # Success resets everything
    throttle.success("ip1")
    assert throttle.remaining("ip1", now=now) == 0.0
    
    # Max lock limit
    throttle.max_lock_sec = 2.0
    throttle.failure("ip2", now=now)
    throttle.failure("ip2", now=now)
    lock = throttle.failure("ip2", now=now)
    assert lock == 2.0  # Capped at max_lock_sec
