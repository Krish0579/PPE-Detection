from __future__ import annotations

import random

from src.video.connection import (
    CameraConnection,
    ConnectionState,
    ReconnectPolicy,
)


def test_reconnect_policy_backoff():
    policy = ReconnectPolicy(base_backoff_sec=1.0, max_backoff_sec=10.0, jitter_ratio=0.0)
    assert policy.backoff(1) == 1.0
    assert policy.backoff(2) == 2.0
    assert policy.backoff(3) == 4.0
    assert policy.backoff(4) == 8.0
    assert policy.backoff(5) == 10.0  # max

def test_reconnect_policy_jitter():
    policy = ReconnectPolicy(base_backoff_sec=1.0, max_backoff_sec=10.0, jitter_ratio=0.5)
    rng = random.Random(42)
    b1 = policy.backoff(1, rng=rng)
    assert 0.5 <= b1 <= 1.5

def test_camera_connection_start_stop():
    conn = CameraConnection(camera_id="cam1")
    assert conn.state == ConnectionState.DISCONNECTED

    conn.start(now=0.0)
    assert conn.state == ConnectionState.CONNECTING
    assert conn.attempts == 1

    conn.stop(now=1.0)
    assert conn.state == ConnectionState.DISCONNECTED

def test_camera_connection_on_frame():
    conn = CameraConnection(camera_id="cam1")
    conn.start(now=0.0)
    
    conn.on_frame(now=1.0)
    assert conn.state == ConnectionState.CONNECTED
    assert conn.ever_connected is True
    assert conn.attempts == 0
    assert conn.is_fresh is True

def test_camera_connection_tick_timeout():
    policy = ReconnectPolicy(connect_timeout_sec=5.0)
    conn = CameraConnection(camera_id="cam1", policy=policy)
    
    conn.start(now=0.0)
    
    assert not conn.tick(now=1.0)
    assert conn.state == ConnectionState.CONNECTING
    
    assert not conn.tick(now=5.1)
    assert conn.state == ConnectionState.RECONNECTING
    assert conn.last_error == "connection timeout"

def test_camera_connection_degraded_and_dead():
    policy = ReconnectPolicy(stale_after_sec=2.0, dead_after_sec=10.0)
    conn = CameraConnection(camera_id="cam1", policy=policy)
    
    conn.start(now=0.0)
    conn.on_frame(now=1.0)
    
    # Still fresh
    assert not conn.tick(now=2.0)
    assert conn.state == ConnectionState.CONNECTED
    
    # Degraded
    assert not conn.tick(now=3.1)
    assert conn.state == ConnectionState.DEGRADED
    
    # Dead
    assert not conn.tick(now=11.1)
    assert conn.state == ConnectionState.RECONNECTING

def test_camera_connection_reconnect_flow():
    policy = ReconnectPolicy(connect_timeout_sec=5.0, base_backoff_sec=1.0, jitter_ratio=0.0)
    conn = CameraConnection(camera_id="cam1", policy=policy)
    
    conn.start(now=0.0)
    conn.on_error(now=1.0, error="stream failed")
    
    assert conn.state == ConnectionState.RECONNECTING
    assert conn.next_retry_at == 2.0  # now + 1.0 backoff
    
    # Not time yet
    assert not conn.tick(now=1.5)
    
    # Time to retry
    assert conn.tick(now=2.1)
    assert conn.state == ConnectionState.CONNECTING
    assert conn.attempts == 2

def test_camera_connection_max_attempts():
    policy = ReconnectPolicy(max_attempts=3, jitter_ratio=0.0)
    conn = CameraConnection(camera_id="cam1", policy=policy)
    conn.start(now=0.0)
    
    # Attempt 1 -> fails
    conn.on_error(now=1.0)
    assert conn.state == ConnectionState.RECONNECTING
    
    # Attempt 2 -> tick advances state
    conn.tick(now=conn.next_retry_at + 0.1)
    assert conn.state == ConnectionState.CONNECTING
    assert conn.attempts == 2
    
    # Attempt 2 -> fails
    conn.on_error(now=2.0)
    assert conn.state == ConnectionState.RECONNECTING
    
    # Attempt 3 -> tick advances state
    conn.tick(now=conn.next_retry_at + 0.1)
    assert conn.state == ConnectionState.CONNECTING
    assert conn.attempts == 3
    
    # Attempt 3 -> fails
    conn.on_error(now=3.0)
    assert conn.state == ConnectionState.RECONNECTING
    
    # Next tick exceeds max attempts -> stops
    assert not conn.tick(now=conn.next_retry_at + 0.1)
    assert conn.state == ConnectionState.DISCONNECTED
