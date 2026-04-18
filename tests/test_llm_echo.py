import pytest

from jarvis.llm.base import ChatMessage
from jarvis.llm.echo import EchoProvider


@pytest.mark.asyncio
async def test_echo_chat():
    p = EchoProvider()
    result = await p.chat([ChatMessage(role="user", content="hello")])
    assert result.content == "hello"


@pytest.mark.asyncio
async def test_echo_stream():
    p = EchoProvider()
    chunks = []
    async for c in p.stream([ChatMessage(role="user", content="hi there")]):
        chunks.append(c)
    assert "".join(chunks) == "hi there"
