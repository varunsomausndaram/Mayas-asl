import pytest

from jarvis.voice.conversation import VoiceSession, VoiceState


@pytest.mark.asyncio
async def test_interrupt_sets_state():
    session = VoiceSession(session_id="s1")
    await session.begin_speaking("Hello world")
    active = await session.interrupt()
    assert active == 0
    assert session.state == VoiceState.INTERRUPTED


@pytest.mark.asyncio
async def test_resume_plan():
    session = VoiceSession(session_id="s1")
    u = await session.begin_speaking("Step one. Step two.")
    await session.record_chunk_played(u.index, chunks=1)
    await session.end_speaking(u.index, interrupted=True)
    plan = session.resume_plan()
    assert plan is not None
    assert plan.index == u.index
    assert plan.interrupted is True
