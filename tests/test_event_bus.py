from __future__ import annotations

from src.core.events import EventBus


def test_subscribe_publish():
    bus = EventBus()
    received = []

    def handler(payload):
        received.append(payload)

    unsubscribe = bus.subscribe("test.topic", handler)
    delivered = bus.publish("test.topic", {"msg": "hello"})

    assert delivered == 1
    assert received == [{"msg": "hello"}]

    unsubscribe()
    delivered_after = bus.publish("test.topic", {"msg": "hello2"})
    assert delivered_after == 0
    assert len(received) == 1

def test_subscriber_isolation():
    bus = EventBus()
    received = []

    def good_handler(payload):
        received.append(payload)

    def bad_handler(payload):
        raise ValueError("I failed")

    bus.subscribe("test.topic", bad_handler)
    bus.subscribe("test.topic", good_handler)

    delivered = bus.publish("test.topic", {"msg": "hello"})

    assert delivered == 1
    assert len(received) == 1
    assert bus.failures == 1
