import asyncio
from typing import Callable, Awaitable


async def run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None:
    if not tasks:
        return

    queue: asyncio.Queue = asyncio.Queue()
    for task in tasks:
        queue.put_nowait(task)

    async def worker() -> None:
        while True:
            try:
                task = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                await task()
            finally:
                queue.task_done()

    n_workers = min(max_concurrent, len(tasks))
    worker_tasks = [asyncio.create_task(worker()) for _ in range(n_workers)]

    try:
        await asyncio.gather(*worker_tasks)
    except asyncio.CancelledError:
        for w in worker_tasks:
            if not w.done():
                w.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        raise
