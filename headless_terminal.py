import fcntl
import os
import pty
import struct
import subprocess
import termios
import threading
import time

import pyte


class BaseTerminal:
    def send_keys(self, keys: str) -> None:
        raise NotImplementedError

    def get_screen(self) -> str:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class HeadlessTerminal(BaseTerminal):
    def __init__(self, cols: int = 80, rows: int = 24):
        self.cols = cols
        self.rows = rows
        self._lock = threading.Lock()
        self._closed = False

        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)

        master_fd, slave_fd = pty.openpty()

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        self._process = subprocess.Popen(
            ["/bin/bash", "--login", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            env={
                **os.environ,
                "TERM": "xterm-256color",
                "COLUMNS": str(cols),
                "LINES": str(rows),
            },
        )

        os.close(slave_fd)
        self._master_fd = master_fd

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        self._wait_for_prompt()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                data = os.read(self._master_fd, 4096)
                with self._lock:
                    self.stream.feed(data)
            except OSError:
                break

    def _wait_for_prompt(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.05)
            screen = self.get_screen()
            if "$" in screen or "#" in screen:
                return

    def send_keys(self, keys: str) -> None:
        data = keys.encode() if isinstance(keys, str) else keys
        os.write(self._master_fd, data)

    def get_screen(self) -> str:
        with self._lock:
            return "\n".join(self.screen.display)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._process.terminate()
            self._process.wait(timeout=3)
        except Exception:
            self._process.kill()
        try:
            os.close(self._master_fd)
        except OSError:
            pass
