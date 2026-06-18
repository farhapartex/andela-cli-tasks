import time
import pytest
from headless_terminal import HeadlessTerminal


@pytest.fixture
def terminal():
    t = HeadlessTerminal()
    yield t
    t.close()


def wait_for(terminal, text, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in terminal.get_screen():
            return True
        time.sleep(0.05)
    return False


def test_terminal_starts_with_bash_prompt(terminal):
    screen = terminal.get_screen()
    assert "$" in screen or "#" in screen


def test_send_command_and_read_output(terminal):
    terminal.send_keys("echo hello_world\n")
    assert wait_for(terminal, "hello_world")


def test_multiline_output(terminal):
    terminal.send_keys("echo line1 && echo line2\n")
    assert wait_for(terminal, "line1")
    assert wait_for(terminal, "line2")


def test_ctrl_c_interrupts_running_command(terminal):
    terminal.send_keys("sleep 60\n")
    time.sleep(0.2)
    terminal.send_keys("\x03")
    assert wait_for(terminal, "$")


def test_ctrl_d_exits_interactive_python(terminal):
    terminal.send_keys("python3 -c 'import sys; sys.stdout.write(\"py_ready\\n\"); sys.stdout.flush(); input()'\n")
    assert wait_for(terminal, "py_ready")
    terminal.send_keys("\x04")
    assert wait_for(terminal, "$")


def test_interactive_program_python_repl(terminal):
    terminal.send_keys("python3\n")
    assert wait_for(terminal, ">>>")
    terminal.send_keys("1 + 1\n")
    assert wait_for(terminal, "2")
    terminal.send_keys("exit()\n")
    assert wait_for(terminal, "$")


def test_environment_variable(terminal):
    terminal.send_keys("export MY_VAR=test123 && echo $MY_VAR\n")
    assert wait_for(terminal, "test123")


def test_command_chaining(terminal):
    terminal.send_keys("cd /tmp && pwd\n")
    assert wait_for(terminal, "/tmp")


def test_close_is_idempotent(terminal):
    terminal.close()
    terminal.close()


def test_get_screen_returns_string(terminal):
    screen = terminal.get_screen()
    assert isinstance(screen, str)
    assert len(screen) > 0


def test_modifier_key_ctrl_l_clears_screen(terminal):
    terminal.send_keys("echo before_clear\n")
    assert wait_for(terminal, "before_clear")
    terminal.send_keys("\x0c")
    time.sleep(0.2)
    screen = terminal.get_screen()
    assert "before_clear" not in screen
