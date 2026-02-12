from __future__ import annotations

import pytest

from omni.foundation.utils.asyncio import run_async_blocking


def test_run_async_blocking_without_running_loop() -> None:
    async def _sample() -> int:
        return 7

    assert run_async_blocking(_sample()) == 7


@pytest.mark.asyncio
async def test_run_async_blocking_with_running_loop() -> None:
    async def _sample() -> int:
        return 42

    assert run_async_blocking(_sample()) == 42
