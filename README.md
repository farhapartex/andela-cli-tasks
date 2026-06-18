# andela_tasks

A set of programming tasks I worked on. Each one is self-contained.

---

## 1. Cancel Async Tasks

**What the problem is**

I needed a function called `run_tasks` that takes a list of async tasks and a number called `max_concurrent`. It runs all the tasks but makes sure no more than `max_concurrent` tasks are running at the same time. One important thing was that if someone cancels the run with Ctrl+C, the cleanup code inside each task should still run properly.

**How I solved it**

I used a worker pool backed by an asyncio queue. All tasks go into the queue at the start. Then I spin up exactly `max_concurrent` worker coroutines. Each worker pulls a task from the queue, runs it, and immediately picks the next one when done. When cancellation happens, I catch the `CancelledError`, cancel the remaining workers, and wait for them to finish before re-raising. This makes sure `finally` blocks and `async with` cleanup code in tasks always run.

**Time complexity and language**

Python. Scheduling is O(n) where n is the number of tasks. Memory is O(max_concurrent) because only that many tasks are alive at once, not all n.

**How to run**

```python
from cancel_async_tasks import run_tasks
import asyncio

async def my_task():
    await asyncio.sleep(1)

asyncio.run(run_tasks([my_task] * 10, max_concurrent=3))
```

To run tests:

```bash
pytest tests/test_run_tasks.py
```

---

## 2. Git Leak Recovery

**What the problem is**

A secret was accidentally committed to a git repo at `/app/repo` and then someone tried to remove it by rewriting history. The secret is in the format `secret[...]`. I needed to recover it, write it to `/app/secret.txt`, and then fully clean it from the repo so it cannot be found again. Normal files and commit messages should stay untouched.

**How I solved it**

When git history is rewritten, the old objects do not get deleted immediately. They become dangling objects still sitting in `.git/objects`. I used `git cat-file --batch-all-objects` to scan every object in the repo including unreachable ones, then searched for the `secret[...]` pattern. After writing the secret to a file, I cleaned the repo by expiring all reflog entries with `git reflog expire --expire=now --all` and then running `git gc --prune=now --aggressive` to remove the dangling objects permanently.

**Time complexity and language**

Python. Scanning all objects is O(n) where n is the number of objects in the repo. The order matters: recover first, clean second.

**How to run**

```python
from git_leak_recovery import recover

recover()  # uses /app/repo and writes to /app/secret.txt
```

Or with custom paths:

```python
recover(repo="/path/to/repo", secret_file="/path/to/secret.txt")
```

To run tests:

```bash
pytest tests/test_git_leak_recovery.py
```

---

## 3. Headless Terminal

**What the problem is**

I needed to implement a `HeadlessTerminal` class that extends a `BaseTerminal` interface. It should act like a real terminal running an interactive bash shell. It should support typing commands, running interactive programs, sending modifier keys like Ctrl+C, and sourcing startup files like `~/.bashrc`.

**How I solved it**

The core of this is a PTY (pseudo-terminal). A PTY gives you a master and a slave file descriptor. I hand the slave to bash so it thinks it has a real terminal. My code writes to the master to send keystrokes and reads from it to get output. I used the `pyte` library to parse the ANSI escape sequences from the output and maintain a virtual 80x24 screen. A background thread reads from the PTY continuously. Because bash gets `-i` and `--login` flags, it sources the startup files. Modifier keys like `\x03` just flow through as raw bytes, so Ctrl+C works naturally.

**Time complexity and language**

Python. No interesting algorithmic complexity here. The screen buffer is always 80x24 regardless of how many commands you run.

**How to run**

```python
from headless_terminal import HeadlessTerminal

t = HeadlessTerminal()
t.send_keys("echo hello\n")
print(t.get_screen())
t.close()
```

To run tests:

```bash
pytest tests/test_headless_terminal.py
```

---

## 4. KV Store with gRPC

**What the problem is**

I needed to build a key-value store server using gRPC. The store maps string keys to integer values. It has two operations: `SetVal` to store a value and `GetVal` to retrieve one. The server should run on port 5328.

**How I solved it**

I wrote a proto file defining the `KVStore` service with the two RPC methods. Then I generated the Python bindings using `grpc_tools.protoc`. The server class uses a plain Python dict as the store. `SetVal` writes to the dict and returns the value. `GetVal` reads from it and returns 0 if the key does not exist. The server runs with a thread pool executor to handle concurrent requests.

**Time complexity and language**

Python. Both `GetVal` and `SetVal` are O(1) dict operations.

**How to run**

First start the server:

```bash
cd kv_store_grpc
python3 server.py
```

To run tests (server must be running):

```bash
pytest kv_store_grpc/tests/test_kv_store.py
```

---

## 5. PyPI Server

**What the problem is**

I needed to create a Python package called `vectorops` with version `0.1.0`, build it, and host it on a local PyPI server running on port 8080. The package should have a `dotproduct` function that computes the dot product of two lists of numbers. Anyone should be able to install it with `pip install --index-url http://localhost:8080/simple vectorops==0.1.0`.

**How I solved it**

I created the `vectorops` package with a `dotproduct` function in `__init__.py`. I wrote a `pyproject.toml` with the package name and version, then built it with `python -m build` which produced a wheel file. I used `pypiserver` to host the packages directory. It implements the Simple Repository API that pip expects, so `--index-url` works out of the box.

**Time complexity and language**

Python. The `dotproduct` function is O(n) where n is the length of the input lists.

**How to run**

Build the package and start the server:

```bash
cd pypi_server
python3 -m build
cp dist/vectorops-0.1.0-py3-none-any.whl packages/
python3 -m pypiserver run -p 8080 packages/
```

Install from the local server:

```bash
pip install --index-url http://localhost:8080/simple vectorops==0.1.0
```

Verify it works:

```bash
python3 -c "from vectorops import dotproduct; print(dotproduct([1, 1], [0, 1]))"
```
