#!/usr/bin/env python3
"""Real-PTY smoke test for lib/terminal_host.py.

Runs a shell, types a line, pastes two lines, checks the written file, captures
a PNG, records a short clip and verifies the MP4 decodes, reads a tracked exit
code (including two consecutive zeros), exits with status 7, and verifies a
SIGTERM cleans up the whole shell process group.

    python3 tests/pty_smoke.py [--plugin DIR] [--keep]
"""
import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent


class Driver:
    """JSON-lines driver that reads raw bytes, so select never misses buffered lines."""

    def __init__(self, plugin, root, cols=100, rows=31):
        self.root = root
        self.id = 0
        self.pending = b""
        self.queue = []
        self.workspace = root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assets = root / "run"
        self.live = root / "live"
        env = dict(os.environ)
        env.update(TERM="xterm-256color", LANG="en_US.UTF-8")
        env.pop("PROMPT_COMMAND", None)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(plugin / "lib" / "terminal_host.py"),
             "--workspace", str(self.workspace), "--assets", str(self.assets),
             "--live", str(self.live), "--id", "t1", "--shell", "/bin/bash",
             "--cols", str(cols), "--rows", str(rows), "--track-exit", "--norc"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, bufsize=0)

    def _line(self, timeout):
        deadline = time.time() + timeout
        while True:
            if b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                return line
            remain = deadline - time.time()
            if remain <= 0:
                raise TimeoutError("等待终端消息超时")
            ready, _, _ = select.select([self.proc.stdout], [], [], min(0.2, remain))
            if ready:
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if not chunk:
                    return None
                self.pending += chunk
                continue
            if self.proc.poll() is not None and not self.pending:
                return None

    def read(self, timeout=30):
        line = self._line(timeout)
        if line is None:
            raise EOFError("终端进程已结束")
        try:
            return json.loads(line)
        except ValueError:
            return self.read(timeout)

    def send(self, action, timeout=45, **fields):
        request = self.id + 1
        payload = {"id": request, "action": action, **fields}
        self.proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        self.proc.stdin.flush()
        deadline = time.time() + timeout
        for index, message in enumerate(self.queue):
            if message.get("id") == request:
                self.queue.pop(index)
                self.id = request
                return self._checked(action, message)
        while time.time() < deadline:
            message = self.read(max(1, deadline - time.time()))
            if message.get("id") == request:
                self.id = request
                return self._checked(action, message)
            self.queue.append(message)
        raise TimeoutError("等待 %s 回复超时" % action)

    @staticmethod
    def _checked(action, message):
        if "error" in message:
            raise RuntimeError(action + " 失败：" + message["error"])
        return message

    def wait_kind(self, kind, timeout=40):
        for index, message in enumerate(self.queue):
            if message.get("kind") == kind:
                self.queue.pop(index)
                return message
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self.read(max(1, deadline - time.time()))
            if message.get("kind") == kind:
                return message
            self.queue.append(message)
        raise TimeoutError("没有等到 %s" % kind)

    def close(self):
        """Ask the host to close, then reap it with a bounded wait."""
        errors = []
        if self.proc.poll() is None:
            try:
                self.send("close", timeout=20)
            except Exception as e:  # the host may have exited on its own first
                errors.append(str(e))
        try:
            out, err = self.proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, err = self.proc.communicate(timeout=15)
            errors.append("宿主未按时退出，已强制结束")
        return errors, err.decode("utf-8", "replace")


def wait_exit(driver, expected, previous=None, timeout=20):
    deadline = time.time() + timeout
    state = None
    while time.time() < deadline:
        state = driver.send("state")
        if (state.get("exitConfirmed") and state.get("lastExitCode") == expected
                and (previous is None or state.get("lastExitRevision", 0) > previous)):
            return state
        time.sleep(0.12)
    raise AssertionError("没有拿到新的退出码 %r：%r" % (expected, state))


def pid_gone(pid):
    time.sleep(0.3)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", default=str(PLUGIN))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    plugin = Path(args.plugin).resolve()
    root = Path(tempfile.mkdtemp(prefix="paiwarp-smoke-"))
    (root / "second").mkdir()
    problems = []
    driver = other = None
    try:
        driver = Driver(plugin, root)
        ready = driver.wait_kind("ready", 40)
        assert Path(ready["workspace"]).resolve() == driver.workspace.resolve(), ready
        assert ready["shell"] == "/bin/bash", ready

        state = driver.send("input", kind="line", data="printf 'hello-paiwarp\\n'")
        for _ in range(20):
            if "hello-paiwarp" in state["screen"]:
                break
            state = driver.send("state")
            time.sleep(0.2)
        assert "hello-paiwarp" in state["screen"], "屏幕没有出现命令输出"

        shot = driver.send("capture", label="smoke")
        image = driver.workspace / shot["path"]
        assert image.is_file() and image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", shot

        note = "第一行\nsecond line"
        driver.send("input", kind="line", data="cat > notes.txt")
        driver.send("input", kind="paste", data=note + "\n")
        driver.send("input", kind="key", data="ctrl+d")
        deadline = time.time() + 10
        while time.time() < deadline and not (driver.workspace / "notes.txt").exists():
            time.sleep(0.2)
        text = (driver.workspace / "notes.txt").read_text()
        assert text.rstrip("\n") == note, repr(text)

        driver.send("record", state="start")
        driver.send("input", kind="line", data="for i in 1 2 3; do echo tick-$i; sleep 0.5; done")
        time.sleep(0.4)
        rec = driver.send("record", state="stop", timeout=90)
        assert rec.get("mp4"), rec
        video = driver.workspace / rec["mp4"]
        assert video.is_file() and video.stat().st_size > 1000, rec
        assert rec.get("decoded") is True, rec
        probe = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                               capture_output=True, text=True)
        assert probe.returncode == 0 and not probe.stderr.strip(), probe.stderr[-500:]
        assert rec["seconds"] > 1.5, rec

        driver.send("input", kind="line", data="false")
        failed = wait_exit(driver, 1)
        driver.send("input", kind="line", data="true")
        zero = wait_exit(driver, 0, previous=failed["lastExitRevision"])
        driver.send("input", kind="line", data="true")
        wait_exit(driver, 0, previous=zero["lastExitRevision"])

        driver.send("input", kind="line", data="exit 7")
        exited = driver.wait_kind("exit", 30)
        assert exited.get("exitCode") == 7, exited
        try:
            driver.send("close", timeout=10)
        except Exception:
            pass
        closed = driver.wait_kind("closed", 30)
        assert closed.get("terminal") == "t1", closed
        assert closed.get("exitCode") == 7, closed
        assert pid_gone(ready["pid"]), "shell 进程 %s 没有清理" % ready["pid"]
        errors, stderr = driver.close()
        assert driver.proc.returncode == 0, (driver.proc.returncode, errors, stderr[-800:])

        large = Driver(plugin, root / "large", cols=200, rows=60)
        large_ready = large.wait_kind("ready", 40)
        large_state = large.send("state")
        assert large_state["viewWidth"] > 1160 and large_state["viewHeight"] > 794, large_state
        assert large_state["screenWidth"] <= large_state["viewWidth"], large_state
        assert large_state["screenHeight"] <= large_state["viewHeight"], large_state
        large.send("input", kind="line", data="for i in $(seq 1 60); do echo row-$i; done")
        for _ in range(60):
            large_state = large.send("state")
            if "row-60" in large_state["screen"]:
                break
            time.sleep(0.15)
        assert "row-60" in large_state["screen"], "60 行终端最后一行不可见"
        large_shot = large.send("capture", label="large")
        png = (large.workspace / large_shot["path"]).read_bytes()
        width = int.from_bytes(png[16:20], "big")
        height = int.from_bytes(png[20:24], "big")
        assert (width, height) == (large_state["viewWidth"], large_state["viewHeight"]), (width, height, large_state)
        assert width > 1900 and height > 1100, (width, height)
        large.send("close", timeout=20)
        large.wait_kind("closed", 30)
        errors_large, stderr_large = large.close()
        assert large.proc.returncode == 0, (errors_large, stderr_large[-600:])
        assert pid_gone(large_ready["pid"]), "大尺寸终端 shell 没有清理"

        other = Driver(plugin, root / "second")
        other_ready = other.wait_kind("ready", 40)
        other.proc.terminate()
        errors2, stderr2 = other.close()
        assert other.proc.returncode is not None, (errors2, stderr2[-800:])
        assert pid_gone(other_ready["pid"]), "SIGTERM 后 shell 进程 %s 没有清理" % other_ready["pid"]
    except Exception as e:
        problems.append("%s: %s" % (type(e).__name__, e))
    finally:
        for name, item in (("main", driver), ("second", other)):
            if item is not None:
                try:
                    errors, stderr = item.close()
                    if errors or stderr.strip():
                        problems.append("%s 关闭诊断：%s %s" % (name, errors, stderr[-600:]))
                except Exception as e:
                    problems.append("%s 关闭失败：%s" % (name, e))
        if args.keep or problems:
            print("保留测试目录：%s" % root)
        else:
            shutil.rmtree(root, ignore_errors=True)
    if problems:
        for problem in problems:
            print("FAIL", problem)
        return 1
    print("PASS real PTY: input, paste, file bytes, PNG, MP4 decode, fresh exit codes, signal cleanup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
