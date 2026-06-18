import asyncio
import time
import pytest
from cancel_async_tasks import run_tasks


@pytest.mark.asyncio
async def test_all_tasks_execute():
    executed = []

    async def task(n):
        await asyncio.sleep(0.01)
        executed.append(n)

    await run_tasks([lambda i=i: task(i) for i in range(10)], max_concurrent=3)
    assert sorted(executed) == list(range(10))


@pytest.mark.asyncio
async def test_concurrency_cap_is_never_exceeded():
    active = []
    peak = [0]

    async def task():
        active.append(1)
        peak[0] = max(peak[0], len(active))
        await asyncio.sleep(0.05)
        active.pop()

    await run_tasks([task] * 20, max_concurrent=4)
    assert peak[0] <= 4


@pytest.mark.asyncio
async def test_parallel_execution_is_faster_than_sequential():
    async def task():
        await asyncio.sleep(0.1)

    start = time.monotonic()
    await run_tasks([task] * 10, max_concurrent=10)
    elapsed = time.monotonic() - start

    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_max_concurrent_one_means_no_overlap():
    active = [0]
    overlaps_detected = [False]

    async def task():
        active[0] += 1
        if active[0] > 1:
            overlaps_detected[0] = True
        await asyncio.sleep(0.02)
        active[0] -= 1

    await run_tasks([task] * 6, max_concurrent=1)
    assert not overlaps_detected[0]


@pytest.mark.asyncio
async def test_empty_task_list_does_not_raise():
    await run_tasks([], max_concurrent=5)


@pytest.mark.asyncio
async def test_max_concurrent_larger_than_task_count():
    results = []

    async def task(n):
        await asyncio.sleep(0.01)
        results.append(n)

    await run_tasks([lambda i=i: task(i) for i in range(3)], max_concurrent=100)
    assert sorted(results) == [0, 1, 2]


@pytest.mark.asyncio
async def test_cleanup_runs_on_cancellation():
    cleaned = []

    async def task():
        try:
            await asyncio.sleep(10)
        finally:
            cleaned.append(True)

    runner = asyncio.create_task(run_tasks([task] * 5, max_concurrent=3))
    await asyncio.sleep(0.05)
    runner.cancel()

    with pytest.raises(asyncio.CancelledError):
        await runner

    assert len(cleaned) > 0


@pytest.mark.asyncio
async def test_simulated_api_batch_fetch():
    fetch_log = []

    async def fetch(endpoint, latency):
        await asyncio.sleep(latency)
        fetch_log.append(endpoint)

    endpoints = [
        ("/users", 0.05),
        ("/orders", 0.03),
        ("/products", 0.07),
        ("/inventory", 0.02),
        ("/reports", 0.06),
        ("/analytics", 0.04),
    ]

    tasks = [lambda e=ep, l=lat: fetch(e, l) for ep, lat in endpoints]

    start = time.monotonic()
    await run_tasks(tasks, max_concurrent=2)
    elapsed = time.monotonic() - start

    assert sorted(fetch_log) == sorted(ep for ep, _ in endpoints)
    assert elapsed < sum(lat for _, lat in endpoints)


@pytest.mark.asyncio
async def test_tasks_with_shared_resource_stay_consistent():
    counter = [0]

    async def increment():
        current = counter[0]
        await asyncio.sleep(0.01)
        counter[0] = current + 1

    await run_tasks([increment] * 5, max_concurrent=1)
    assert counter[0] == 5


@pytest.mark.asyncio
async def test_single_task():
    result = []

    async def task():
        await asyncio.sleep(0.01)
        result.append(42)

    await run_tasks([task], max_concurrent=1)
    assert result == [42]
