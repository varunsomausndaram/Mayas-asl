import pytest

from jarvis.events import Event, EventBus


@pytest.mark.asyncio
async def test_pubsub_prefix():
    bus = EventBus()
    async with await bus.subscribe("foo.") as sub:
        await bus.publish(Event(topic="foo.bar", type="x", data={"v": 1}))
        await bus.publish(Event(topic="baz.qux", type="y"))  # ignored
        got = await sub.queue.get()
        assert got.topic == "foo.bar" and got.data == {"v": 1}


@pytest.mark.asyncio
async def test_unsubscribe_cleans():
    bus = EventBus()
    sub = await bus.subscribe("a.")
    await sub.close()
    # publishing after close should not blow up
    await bus.publish(Event(topic="a.b", type="x"))
