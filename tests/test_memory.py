import pytest

from jarvis.memory.models import Message
from jarvis.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_session_and_messages(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    session = await store.create_session(title="t")
    assert session.id

    msg = Message(session_id=session.id, role="user", content="hi")
    await store.add_message(msg)
    msg2 = Message(session_id=session.id, role="assistant", content="hello")
    await store.add_message(msg2)

    fetched = await store.list_messages(session.id)
    assert [m.content for m in fetched] == ["hi", "hello"]

    all_sessions = await store.list_sessions()
    assert any(s.id == session.id for s in all_sessions)

    dicts = await store.recent_chat_dicts(session.id)
    assert dicts[0]["role"] == "user"

    await store.rename_session(session.id, "renamed")
    s2 = await store.get_session(session.id)
    assert s2.title == "renamed"

    assert await store.delete_session(session.id) is True
    assert await store.get_session(session.id) is None


@pytest.mark.asyncio
async def test_tool_message_roundtrip(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    s = await store.create_session()
    m = Message(
        session_id=s.id,
        role="tool",
        content='{"ok": true}',
        tool_call_id="call_1",
        name="filesystem_read",
    )
    await store.add_message(m)
    got = (await store.list_messages(s.id))[0]
    assert got.role == "tool"
    assert got.tool_call_id == "call_1"
    assert got.name == "filesystem_read"
