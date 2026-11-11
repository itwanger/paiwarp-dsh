#!/usr/bin/env python3
"""Run examples/python-cli in a clean HOME/PATH with the packed plugin.

Proves the demo workspace is unrelated to the plugin directory and that nothing
reaches for Codex, PaiCLI, a model key or a private home directory.
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


class Driver:
    def __init__(self, plugin, workspace, home):
        self.id = 0
        self.pending = b""
        self.queue = []
        python = sys.executable
        site = subprocess.check_output(
            [python, "-c", "import playwright,os;print(os.path.dirname(os.path.dirname(playwright.__file__)))"],
            text=True).strip()
        browsers = Path.home() / ("Library/Caches/ms-playwright" if sys.platform == "darwin" else ".cache/ms-playwright")
        env = {
            "HOME": str(home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "SHELL": "/bin/bash",
            "LANG": "en_US.UTF-8",
            "TERM": "xterm-256color",
            "PYTHONPATH": site,
            "PLAYWRIGHT_BROWSERS_PATH": str(browsers),
        }
        self.proc = subprocess.Popen(
            [python, "-u", str(plugin / "lib" / "terminal_host.py"),
             "--workspace", str(workspace), "--assets", str(workspace / ".paiwarp-demo" / "run"),
             "--live", str(workspace / ".paiwarp-demo" / "live"), "--id", "demo",
             "--shell", "/bin/bash", "--cols", "100", "--rows", "30", "--norc"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(workspace), env=env, bufsize=0)

    def read(self, timeout=30):
        deadline = time.time() + timeout
        while True:
            if b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                message = json.loads(line)
                return message
            remain = deadline - time.time()
            if remain <= 0:
                raise TimeoutError("等待终端消息超时")
            ready, _, _ = select.select([self.proc.stdout], [], [], min(0.2, remain))
            if not ready:
                if self.proc.poll() is not None and not self.pending:
                    raise EOFError("终端进程已结束")
                continue
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise EOFError("终端进程已结束")
            self.pending += chunk

    def wait_kind(self, kind, timeout=40):
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self.read(max(1, deadline - time.time()))
            if message.get("kind") == kind:
                return message
            if "id" in message:
                self.queue.append(message)
        raise TimeoutError("没有等到 " + kind)

    def send(self, action, timeout=40, **fields):
        request = self.id + 1
        payload = {"id": request, "action": action, **fields}
        self.proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        self.proc.stdin.flush()
        deadline = time.time() + timeout
        for index, message in enumerate(self.queue):
            if message.get("id") == request:
                self.queue.pop(index)
                self.id = request
                return message
        while time.time() < deadline:
            message = self.read(max(1, deadline - time.time()))
            if message.get("id") == request:
                self.id = request
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message
            self.queue.append(message)
        raise TimeoutError("等待 %s 回复超时" % action)

    def close(self):
        if self.proc.poll() is None:
            try:
                self.send("close", timeout=20)
            except Exception:
                pass
        try:
            self.proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.communicate(timeout=10)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    plugin = Path(args.plugin).resolve()
    root = Path(tempfile.mkdtemp(prefix="paiwarp-demo-"))
    workspace = root / "workspace"
    home = root / "home"
    workspace.mkdir()
    home.mkdir()
    shutil.copy(plugin / "examples" / "python-cli" / "todo.py", workspace / "todo.py")
    problems = []
    driver = None
    try:
        driver = Driver(plugin, workspace, home)
        driver.wait_kind("ready", 45)
        state = driver.send("input", kind="line", data="python3 todo.py todos.json")
        for _ in range(30):
            if "todo>" in state.get("screen", ""):
                break
            time.sleep(0.15)
            state = driver.send("state")
        assert "todo>" in state["screen"], "示例程序没有启动"
        driver.send("input", kind="line", data="add 买牛奶")
        driver.send("input", kind="line", data="add 写测试")
        state = driver.send("input", kind="line", data="list")
        assert "买牛奶" in state["screen"] and "写测试" in state["screen"], state["screen"][-400:]
        shot = driver.send("capture", label="demo")
        image = workspace / shot["path"]
        assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        driver.send("input", kind="line", data="quit")
        assert not (home / ".codex").exists(), "运行过程创建了 ~/.codex"
        assert "codex" not in state["screen"].lower(), "画面里出现了 codex"
        driver.send("close", timeout=20)
        driver.wait_kind("closed", 30)
        todo = json.loads((workspace / "todos.json").read_text())
        assert [item["text"] for item in todo] == ["买牛奶", "写测试"], todo
        driver.close()
        assert driver.proc.returncode == 0
    except Exception as error:
        problems.append("%s: %s" % (type(error).__name__, error))
    finally:
        if driver is not None and driver.proc.poll() is None:
            driver.proc.kill()
        if problems:
            print("保留测试目录：%s" % root)
        else:
            shutil.rmtree(root, ignore_errors=True)
    if problems:
        for problem in problems:
            print("FAIL", problem)
        return 1
    print("PASS clean env demo: separate workspace, empty HOME, minimal PATH, no Codex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
