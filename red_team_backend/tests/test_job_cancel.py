import asyncio

import pytest

from app.job_runtime import RUNNING_JOBS, cancel_running, spawn


def test_cancel_running_when_idle():
    assert cancel_running("missing-job") is False


@pytest.mark.asyncio
async def test_cancel_running_unregisters_task():
    started = asyncio.Event()

    async def slow() -> None:
        started.set()
        await asyncio.sleep(30)

    spawn("j-reg-endpoint", slow(), target="juice.lab")
    await started.wait()
    assert cancel_running("j-reg-endpoint") is True
    await asyncio.sleep(0.05)
    assert "j-reg-endpoint" not in RUNNING_JOBS
