import pytest

from jarvis.core.permissions import (
    ApprovalDecision,
    PermissionBroker,
    RiskLevel,
    assess,
)


def test_assess_baseline():
    a = assess("web_search", {"query": "x"})
    assert a.overall == RiskLevel.LOW
    assert a.touches_network is True


def test_assess_filesystem_write_outside():
    a = assess("filesystem_write", {"path": "/etc/shadow", "content": "x"})
    assert a.overall == RiskLevel.HIGH
    assert any("writes outside workspace" in r.reason for r in a.risks)


def test_assess_shell_rm_rf():
    a = assess("shell_exec", {"command": " rm -rf /"})
    assert a.overall == RiskLevel.CRITICAL


def test_risk_level_order():
    assert RiskLevel.CRITICAL.at_least(RiskLevel.HIGH)
    assert not RiskLevel.LOW.at_least(RiskLevel.HIGH)


@pytest.mark.asyncio
async def test_broker_auto_approves_low():
    broker = PermissionBroker(auto_approve_below=RiskLevel.MEDIUM)
    a = assess("web_search", {"query": "x"})
    ok, reason = await broker.authorize(a)
    assert ok is True
    assert "threshold" in reason


@pytest.mark.asyncio
async def test_broker_requires_approval():
    async def always_deny(_a):
        return ApprovalDecision.DENIED

    broker = PermissionBroker(auto_approve_below=RiskLevel.MEDIUM, requester=always_deny)
    a = assess("filesystem_write", {"path": "notes.txt", "content": "hi"})
    ok, _ = await broker.authorize(a)
    assert ok is False


@pytest.mark.asyncio
async def test_broker_session_approval():
    calls = {"n": 0}

    async def req(_a):
        calls["n"] += 1
        return ApprovalDecision.APPROVED_SESSION

    broker = PermissionBroker(auto_approve_below=RiskLevel.MEDIUM, requester=req)
    a = assess("filesystem_write", {"path": "notes.txt", "content": "hi"})
    ok, _ = await broker.authorize(a)
    assert ok
    # Second time — no prompt.
    ok2, reason2 = await broker.authorize(a)
    assert ok2
    assert "session" in reason2
    assert calls["n"] == 1
