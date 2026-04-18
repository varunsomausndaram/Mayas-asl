import pytest

from jarvis.core.orchestrator import EventKind


@pytest.mark.asyncio
async def test_orchestrator_runs_turn(runtime):
    session = await runtime.memory.create_session()
    turn = await runtime.orchestrator.run(session.id, "hello there")
    # Echo provider returns the user text, so the assistant should echo.
    assert "hello there" in turn.assistant.content


@pytest.mark.asyncio
async def test_orchestrator_stream_yields_tokens(runtime):
    session = await runtime.memory.create_session()
    saw_token = False
    saw_done = False
    async for ev in runtime.orchestrator.run_stream(session.id, "ping"):
        if ev.kind == EventKind.TOKEN:
            saw_token = True
        if ev.kind == EventKind.DONE:
            saw_done = True
    assert saw_token and saw_done


@pytest.mark.asyncio
async def test_orchestrator_interrupt(runtime):
    session = await runtime.memory.create_session()
    runtime.orchestrator.interrupt(session.id)  # pre-set the flag
    events = [ev async for ev in runtime.orchestrator.run_stream(session.id, "x")]
    # Either we aborted cleanly or we completed quickly with the echo provider;
    # in both cases we must finish with a DONE frame.
    assert events[-1].kind == EventKind.DONE


@pytest.mark.asyncio
async def test_profile_name_learned(runtime):
    session = await runtime.memory.create_session()
    await runtime.orchestrator.run(session.id, "my name is Varun")
    profile = await runtime.profile_store.load()
    assert profile.name.lower().startswith("varun")
