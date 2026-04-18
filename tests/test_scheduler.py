import asyncio
import time

import pytest

from jarvis.scheduler.engine import JobKind, Scheduler, new_job


@pytest.mark.asyncio
async def test_scheduler_persists_and_fires(tmp_path):
    fired: list[str] = []

    async def dispatch(job):
        fired.append(job.id)

    sched = Scheduler(tmp_path / "s.db", dispatch=dispatch, tick_seconds=0.1)
    await sched.start()
    try:
        job = new_job(JobKind.REMINDER, title="t", at_timestamp=time.time() + 0.2, message="m")
        await sched.create(job)
        await asyncio.sleep(0.7)
        assert job.id in fired
        jobs = await sched.list_jobs()
        assert jobs[0].run_count >= 1
    finally:
        await sched.stop()


@pytest.mark.asyncio
async def test_scheduler_delete(tmp_path):
    sched = Scheduler(tmp_path / "s.db")
    await sched.init()
    job = new_job(JobKind.REMINDER, title="t", at_timestamp=time.time() + 60, message="m")
    await sched.create(job)
    assert await sched.delete(job.id) is True
    assert await sched.get(job.id) is None


@pytest.mark.asyncio
async def test_scheduler_validation(tmp_path):
    sched = Scheduler(tmp_path / "s.db")
    await sched.init()
    with pytest.raises(ValueError):
        await sched.create(new_job(JobKind.REMINDER, title="t"))  # no trigger
    with pytest.raises(ValueError):
        await sched.create(
            new_job(JobKind.REMINDER, title="t", cron="0 9 * * *", every_seconds=60)
        )
    with pytest.raises(ValueError):
        await sched.create(new_job(JobKind.PROMPT, title="t", at_timestamp=time.time() + 5))
