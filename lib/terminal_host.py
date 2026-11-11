#!/usr/bin/env python3
"""PaiWarp terminal host.

Runs one real PTY, mirrors it into a headless xterm page, and exposes a small
JSON-lines protocol on stdin/stdout:

  in   {"id": 7, "action": "input", "kind": "line", "data": "ls -la"}
  out  {"id": 7, "revision": 12, "status": "running", "screen": "...", ...}

The process owns exactly one terminal. Closing stdin, SIGTERM, or an explicit
"close" command tears down the PTY, the shell's process group, the renderer and
any active recording.
"""
import argparse
import codecs
import errno
import fcntl
import json
import math
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
import traceback
from pathlib import Path

PORTABLE = Path(__file__).resolve().parent.parent
# Cell metrics for 18px Menlo/PingFang; the real size is measured from xterm
# after the page opens and the viewport grows to fit, so nothing is clipped.
CELL_W, CELL_H = 10.8, 20.16
PAD_X, PAD_Y = 26, 22
COLS, ROWS = 100, 31


def view_size(cols, rows):
    return (max(320, round(cols * CELL_W) + PAD_X), max(200, round(rows * CELL_H) + PAD_Y))

KEYS = {
    "enter": "\r", "return": "\r", "tab": "\t", "shift+tab": "\x1b[Z",
    "esc": "\x1b", "escape": "\x1b", "backspace": "\x7f",
    "ctrl+c": "\x03", "ctrl+d": "\x04", "ctrl+l": "\x0c",
    "ctrl+o": "\x0f", "ctrl+z": "\x1a", "delete": "\x1b[3~",
    "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "home": "\x1b[H", "end": "\x1b[F", "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~", "space": " ",
}

INIT_JS = """([cols,rows]) => {
  window.term = new Terminal({cols,rows,minimumContrastRatio:7,fontSize:18,
    lineHeight:1.12,fontFamily:'Menlo, PingFang SC, monospace',scrollback:2000,
    theme:{background:'#14171c',foreground:'#e4e9f1',cursor:'#95beff'}});
  term.open(document.querySelector('#term'));
  window.replies = [];
  term.onData(d => replies.push(d));
  document.body.style.background = '#14171c';
}"""

SCREEN_JS = """() => {const b=term.buffer.active; return Array.from(
  {length:term.rows},(_,i)=>b.getLine(b.viewportY+i)?.translateToString(true)||'').join('\\n')}"""


def atomic(path, data):
    temp = path.with_name("." + path.name + ".part")
    temp.write_bytes(data)
    os.replace(temp, path)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Host:
    def __init__(self, opts):
        self.workspace = Path(opts.workspace).resolve()
        self.assets = Path(opts.assets).resolve()
        self.live = Path(opts.live).resolve()
        self.term_id = opts.id
        self.run_label = getattr(opts, 'run_label', None) or ''
        self.shell = opts.shell
        self.cols, self.rows = opts.cols, opts.rows
        self.track_exit = opts.track_exit
        self.norc = bool(getattr(opts, 'norc', False))
        self.recording_wanted = bool(getattr(opts, 'recording_wanted', False))
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.raw = ""
        self.base = 0
        self.revision = 0
        self.exit_info = None
        self.paused = False
        self.closing = None
        self.fd = None
        self.pid = None
        self.play = self.browser = self.page = None
        self.rec_ctx = self.rec_page = self.rec_video = None
        self.rec_started = None
        self.captures = 0
        self.recordings = 0
        self.view_w, self.view_h = view_size(self.cols, self.rows)
        self.screen_w = self.screen_h = 0
        self.next_frame = 0.0
        self.next_state = 0.0
        self.last_output = time.monotonic()
        self.started = time.time()
        self.inbuf = b""
        self.exit_file = self.live / (self.term_id + ".exit")
        self.last_exit_code = None
        self.last_exit_revision = None
        self.exit_pending = False
        self.exit_invalidated_at = 0.0

    # ---------- startup ----------

    def start(self):
        for path in (self.assets / "screenshots", self.assets / "video", self.live):
            path.mkdir(parents=True, exist_ok=True)
        self.open_view()
        self.fork_shell()
        self.measure_view()
        self.emit({"kind": "ready", "terminal": self.term_id, "workspace": str(self.workspace),
                   "shell": self.shell, "cols": self.cols, "rows": self.rows,
                   "pid": self.pid, "startedAt": now_iso()})
        self.state_now()

    def open_view(self):
        from playwright.sync_api import sync_playwright
        self.play = sync_playwright().start()
        self.browser = self.play.chromium.launch()
        self.page = self.new_terminal_page(self.browser, True)

    def measure_view(self):
        try:
            rect = self.page.evaluate(
                "() => {const e=document.querySelector('.xterm-screen'); if(!e) return null;"
                " const r=e.getBoundingClientRect(); return {w:r.width,h:r.height}}")
        except Exception:
            rect = None
        if rect:
            self.screen_w, self.screen_h = math.ceil(rect["w"]), math.ceil(rect["h"])
            self.view_w = max(self.view_w, self.screen_w + PAD_X)
            self.view_h = max(self.view_h, self.screen_h + PAD_Y)
        self.page.set_viewport_size({"width": self.view_w, "height": self.view_h})

    def new_terminal_page(self, owner, set_viewport=True):
        page = owner.new_page(viewport={"width": self.view_w, "height": self.view_h}) if set_viewport else owner.new_page()
        page.set_default_timeout(15000)
        page.goto((PORTABLE / "terminal.html").as_uri())
        page.add_style_tag(path=str(PORTABLE / "vendor" / "xterm" / "xterm.css"))
        page.add_script_tag(path=str(PORTABLE / "vendor" / "xterm" / "xterm.js"))
        page.evaluate(INIT_JS, [self.cols, self.rows])
        return page

    def fork_shell(self):
        env = dict(os.environ)
        env.update(TERM="xterm-256color", COLORTERM="truecolor")
        env.setdefault("LANG", "en_US.UTF-8")
        if self.track_exit and self.shell.endswith("bash"):
            env["PAIWARP_EXIT_FILE"] = str(self.exit_file)
            hook = 'printf "%s" "$?" > "$PAIWARP_EXIT_FILE"'
            env["PROMPT_COMMAND"] = hook + ("; " + env["PROMPT_COMMAND"] if env.get("PROMPT_COMMAND") else "")
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            try:
                os.chdir(self.workspace)
                args = [self.shell]
                if self.norc:
                    args += (["--noprofile", "--norc"] if self.shell.endswith("bash") else ["-f"])
                args.append("-i")
                os.execvpe(self.shell, args, env)
            except BaseException:
                os._exit(127)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))

    # ---------- io ----------

    def write_fd(self, text):
        data = memoryview(text.encode())
        while data:
            data = data[os.write(self.fd, data):]

    def feed(self, data):
        text = self.decoder.decode(data)
        if not text:
            return
        self.raw += text
        self.trim_raw()
        self.revision += 1
        self.last_output = time.monotonic()
        try:
            self.write_page(self.page, text, answers=True)
            if self.rec_page is not None:
                self.write_page(self.rec_page, text, answers=False)
        except Exception as e:
            self.emit({"kind": "warning", "message": "渲染页面异常：" + str(e)})

    def write_page(self, page, text, answers=False):
        page.evaluate("s => new Promise(done => term.write(s, done))", text)
        if not answers:
            return
        for reply in page.evaluate("() => replies.splice(0)"):
            self.write_fd(reply)

    def trim_raw(self):
        limit = 2_000_000
        if len(self.raw) <= limit:
            return
        cut = self.raw.find("\n", len(self.raw) - limit)
        cut = len(self.raw) - limit if cut < 0 else cut + 1
        self.base += cut
        self.raw = self.raw[cut:]

    def pump(self, timeout=0.05):
        self.read_commands()
        if self.closing:
            return
        if self.fd is not None:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if ready:
                try:
                    data = os.read(self.fd, 65536)
                except OSError as e:
                    if e.errno != errno.EIO:
                        raise
                    data = b""
                if data:
                    self.feed(data)
                else:
                    self.reap()
        if self.exit_info is None:
            self.reap(nonblocking=True)
        now = time.monotonic()
        if now >= self.next_frame:
            self.next_frame = now + 0.7
            self.snapshot()
        if now >= self.next_state:
            self.next_state = now + 0.5
            self.state_now()

    def reap(self, nonblocking=False):
        if self.pid is None:
            return
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG if nonblocking else 0)
        except ChildProcessError:
            pid, status = self.pid, 0
        if pid == 0:
            return
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        code = os.waitstatus_to_exitcode(status)
        signal_no = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
        self.exit_info = {"exitCode": code, "signal": signal_no, "endedAt": now_iso()}
        self.emit({"kind": "exit", **self.exit_info})
        self.finish_recording()
        self.closing = "终端进程已退出"

    def read_commands(self):
        if not select.select([0], [], [], 0)[0]:
            return
        chunk = os.read(0, 65536)
        if not chunk:
            self.closing = "宿主连接已关闭"
            return
        self.inbuf += chunk
        while b"\n" in self.inbuf:
            line, self.inbuf = self.inbuf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                command = json.loads(line)
            except ValueError:
                continue
            try:
                self.handle(command)
            except Exception as e:  # keep one bad command from killing the terminal
                traceback.print_exc(file=sys.stderr)
                self.reply(command.get("id"), {"error": f"{type(e).__name__}: {e}"})

    def handle(self, command):
        action = command.get("action")
        ident = command.get("id")
        if action == "input":
            if self.is_submit(command):
                self.mark_submit()
            self.send_input(command)
            self.settle(command.get("settleMs") or 220)
            self.state_now()
            self.reply(ident, self.state(since=command.get("since")))
        elif action == "state":
            self.reply(ident, self.state(since=command.get("since"), tail=command.get("tail")))
        elif action == "capture":
            self.reply(ident, self.capture(command.get("label")))
        elif action == "record":
            if command.get("state") == "start":
                self.reply(ident, self.start_recording())
            else:
                self.reply(ident, self.stop_recording())
        elif action == "pause":
            self.paused = True
            self.state_now()
            self.reply(ident, self.state())
        elif action == "resume":
            self.paused = False
            self.state_now()
            self.reply(ident, self.state())
        elif action == "resize":
            self.resize(int(command["cols"]), int(command["rows"]))
            self.reply(ident, self.state())
        elif action == "close":
            self.closing = "已收到关闭请求"
            self.reply(ident, self.state())
        elif action == "ping":
            self.reply(ident, {"ok": True})
        else:
            self.reply(ident, {"error": "未知操作"})

    @staticmethod
    def is_submit(command):
        kind = command.get("kind") or "line"
        if kind == "line":
            return True
        name = str(command.get("data") or command.get("key") or "").lower()
        return kind == "key" and name in ("enter", "return")

    def mark_submit(self):
        """A new command line invalidates the previous exit code."""
        if not self.track_exit:
            return
        self.exit_pending = True
        self.last_exit_code = None
        self.last_exit_revision = None
        self.exit_invalidated_at = time.time()
        try:
            self.exit_file.unlink()
        except OSError:
            pass

    def send_input(self, command):
        kind = command.get("kind") or "line"
        if kind == "key":
            name = str(command.get("data") or command.get("key") or "").lower()
            if name not in KEYS:
                raise ValueError("未知按键：" + name)
            self.write_fd(KEYS[name])
            return
        text = command.get("data")
        if text is None:
            text = command.get("text")
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("输入文本无效")
        if kind == "line":
            self.type_text(text)
            self.write_fd("\r")
        elif kind == "text":
            self.type_text(text)
        elif kind == "paste":
            bracketed = False
            try:
                bracketed = bool(self.page.evaluate("() => !!(term.modes && term.modes.bracketedPasteMode)"))
            except Exception:
                bracketed = False
            if bracketed:
                self.write_fd("\x1b[200~" + text + "\x1b[201~")
            else:
                self.write_fd(text)
        else:
            raise ValueError("未知输入类型：" + kind)

    def type_text(self, text):
        for start in range(0, len(text), 8):
            self.pump(0.01)
            self.write_fd(text[start:start + 8])
            time.sleep(0.004)

    def settle(self, quiet_ms, cap_ms=10000):
        quiet = max(0.02, quiet_ms / 1000.0)
        deadline = time.monotonic() + cap_ms / 1000.0
        while time.monotonic() < deadline:
            self.pump(0.04)
            if self.exit_info is not None:
                return
            if time.monotonic() - self.last_output >= quiet:
                return

    def resize(self, cols, rows):
        if self.rec_page is not None:
            raise RuntimeError("录制期间不能改变终端尺寸，先停止录屏")
        self.cols, self.rows = max(40, min(240, cols)), max(12, min(90, rows))
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))
        self.page.evaluate("([c,r]) => term.resize(c,r)", [self.cols, self.rows])
        self.view_w, self.view_h = view_size(self.cols, self.rows)
        self.measure_view()
        self.next_frame = 0

    # ---------- observation ----------

    def screen(self):
        try:
            return self.page.evaluate(SCREEN_JS)
        except Exception:
            return ""

    def read_last_exit(self):
        if not self.track_exit:
            return
        try:
            stamp = self.exit_file.stat().st_mtime
        except OSError:
            return
        if stamp + 0.001 < self.exit_invalidated_at:
            return
        try:
            value = int(self.exit_file.read_text().strip() or "0")
        except (OSError, ValueError):
            return
        if self.exit_pending or value != self.last_exit_code:
            self.exit_pending = False
            self.last_exit_code = value
            self.last_exit_revision = self.revision

    def state(self, since=None, tail=None):
        self.read_last_exit()
        cursor = self.base + len(self.raw)
        payload = {
            "terminal": self.term_id, "revision": self.revision, "cursor": cursor,
            "status": "exited" if self.exit_info else "running",
            "paused": self.paused, "screen": self.screen(),
            "cols": self.cols, "rows": self.rows, "shell": self.shell,
            "viewWidth": self.view_w, "viewHeight": self.view_h,
            "screenWidth": self.screen_w, "screenHeight": self.screen_h,
            "recording": self.rec_page is not None,
            "recordStartedAt": self.rec_started,
            "workspace": str(self.workspace),
            "run": self.run_label or self.relative(self.assets),
            "captures": self.captures, "recordings": self.recordings,
            "lastExitCode": self.last_exit_code,
            "lastExitRevision": self.last_exit_revision,
            "exitConfirmed": self.track_exit and not self.exit_pending and self.last_exit_code is not None,
        }
        if self.exit_info:
            payload.update(self.exit_info)
        if tail:
            payload["output"] = self.raw[-int(tail):]
            payload["truncated"] = len(self.raw) > int(tail)
        elif since is not None:
            since = max(0, int(since) - self.base)
            payload["output"] = self.raw[since:][-8000:]
            payload["truncated"] = len(self.raw) - since > 8000
        return payload

    def snapshot(self):
        try:
            shot = self.page.screenshot(type="jpeg", quality=80)
        except Exception:
            return
        atomic(self.live / (self.term_id + ".jpg"), shot)
        self.state_now()

    def state_now(self):
        try:
            atomic(self.live / (self.term_id + ".json"),
                   json.dumps(self.state(), ensure_ascii=False).encode())
        except Exception:
            pass

    def capture(self, label):
        self.settle(220)
        self.captures += 1
        name = re.sub(r"[^A-Za-z0-9._-]", "-", str(label or ""))[:60]
        name = name or "shot-%02d" % self.captures
        if not name.endswith(".png"):
            name += ".png"
        target = self.assets / "screenshots" / name
        index = 2
        while target.exists():
            target = self.assets / "screenshots" / ("%s-%d.png" % (Path(name).stem, index))
            index += 1
        self.page.screenshot(path=str(target))
        self.state_now()
        return {"kind": "capture", "path": self.relative(target), "bytes": target.stat().st_size,
                "width": self.view_w, "height": self.view_h,
                "screenWidth": self.screen_w, "screenHeight": self.screen_h,
                "revision": self.revision, "at": now_iso(), "captures": self.captures}

    # ---------- recording ----------

    def start_recording(self):
        if self.rec_page is not None:
            raise RuntimeError("已经在录屏")
        self.recordings += 1
        self.rec_started = time.time()
        ctx = self.browser.new_context(viewport={"width": self.view_w, "height": self.view_h},
                                       record_video_dir=str(self.assets / "video"),
                                       record_video_size={"width": self.view_w, "height": self.view_h})
        page = self.new_terminal_page(ctx, False)
        replay = self.raw
        if len(replay) > 400_000:
            cut = replay.find("\n", len(replay) - 400_000)
            replay = replay[cut + 1:] if cut >= 0 else replay[-400_000:]
        if replay:
            page.evaluate("s => term.write(s)", replay)
        self.rec_ctx, self.rec_page = ctx, page
        self.rec_video = page.video
        self.state_now()
        return {"kind": "record", "state": "started", "startedAt": self.rec_started,
                "revision": self.revision}

    def finish_recording(self):
        try:
            if self.rec_ctx is not None:
                self.stop_recording(quiet=True)
        except Exception as e:
            self.emit({"kind": "warning", "message": "结束录屏失败：" + str(e)})

    def stop_recording(self, quiet=False):
        if self.rec_ctx is None:
            if quiet:
                return {}
            raise RuntimeError("当前没有在录屏")
        started = self.rec_started
        ctx, page, video = self.rec_ctx, self.rec_page, self.rec_video
        self.rec_ctx = self.rec_page = self.rec_video = None
        self.rec_started = None
        path = None
        try:
            if page is not None:
                page.close()
            ctx.close()
            path = Path(video.path())
        finally:
            seconds = round(time.time() - started, 2) if started else None
        result = {"kind": "record", "state": "stopped", "seconds": seconds,
                  "webm": self.relative(path), "mp4": None, "decoded": False}
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            result["warning"] = "未安装 ffmpeg/ffprobe，保留 WebM，未生成 MP4"
            self.state_now()
            return result
        mp4 = path.with_suffix(".mp4")
        run = subprocess.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", str(path),
                              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                              str(mp4)], capture_output=True, text=True, timeout=180)
        if run.returncode:
            result["warning"] = "MP4 转码失败：" + (run.stderr or "").strip()[-300:]
            self.state_now()
            return result
        probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nk=1:nw=1", str(mp4)],
                               capture_output=True, text=True, timeout=30)
        result["seconds"] = round(float(probe.stdout.strip() or 0), 2)
        decode = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", str(mp4),
                                 "-f", "null", "-"], capture_output=True, text=True, timeout=180)
        result["decoded"] = decode.returncode == 0 and not decode.stderr.strip()
        result["mp4"] = self.relative(mp4)
        result["bytes"] = mp4.stat().st_size
        if result["decoded"] and result["seconds"] > 0:
            path.unlink(missing_ok=True)
        else:
            result["warning"] = "MP4 解码检查未通过，保留 WebM"
        self.state_now()
        return result

    # ---------- lifecycle ----------

    def relative(self, path):
        try:
            return str(Path(path).resolve().relative_to(self.workspace))
        except ValueError:
            return str(path)

    def reply(self, ident, payload):
        if ident is None:
            return
        self.emit({"id": ident, **payload})

    def emit(self, payload):
        try:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, ValueError):
            self.closing = "宿主连接已关闭"

    def run(self):
        self.start()
        if self.recording_wanted:
            self.start_recording()
        while not self.closing:
            self.pump(0.05)
        self.close()

    def close(self):
        record = None
        if self.rec_ctx is not None:
            try:
                record = self.stop_recording(quiet=True)
            except Exception:
                record = None
        if self.fd is not None and self.exit_info is None:
            self.hangup()
        info = self.exit_info or {"exitCode": None, "signal": None}
        if self.page is not None:
            try:
                self.snapshot()
            except Exception:
                pass
        payload = {"kind": "closed", **info, "verified": self.exit_info is not None,
                   "terminal": self.term_id,
                   "workspace": str(self.workspace), "run": self.relative(self.assets),
                   "seconds": round(time.time() - self.started, 2),
                   "captures": self.captures, "recordings": self.recordings,
                   "recording": record}
        self.emit(payload)
        self.cleanup()

    def hangup(self):
        groups = set()
        try:
            groups.add(os.tcgetpgrp(self.fd))
        except OSError:
            pass
        groups.add(self.pid)
        for group in groups:
            if group and group > 1:
                try:
                    os.killpg(group, signal.SIGHUP)
                except OSError:
                    pass
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and self.exit_info is None:
            self.pump(0.05)
        if self.exit_info is None:
            for target in (self.pid, -self.pid):
                try:
                    os.kill(target, signal.SIGKILL)
                    break
                except OSError:
                    continue
            end = time.monotonic() + 5
            while time.monotonic() < end and self.exit_info is None:
                self.pump(0.05)
            self.reap(nonblocking=True)

    def abort(self):
        """Failure path: the shell's whole process group and renderer must go."""
        try:
            if self.fd is not None and self.exit_info is None:
                self.hangup()
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            if self.browser is not None:
                self.browser.close()
        finally:
            try:
                if self.play is not None:
                    self.play.stop()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--live", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--run", dest="run_label", default=None,
                        help="workspace-relative run directory shown to the panel")
    parser.add_argument("--shell", default=os.environ.get("SHELL") or "/bin/bash")
    parser.add_argument("--cols", type=int, default=COLS)
    parser.add_argument("--rows", type=int, default=ROWS)
    parser.add_argument("--track-exit", action="store_true")
    parser.add_argument("--norc", action="store_true")
    parser.add_argument("--record", action="store_true")
    opts = parser.parse_args()
    opts.recording_wanted = opts.record
    if not sys.platform.startswith(("darwin", "linux")):
        print(json.dumps({"kind": "error", "message": "当前系统没有可用的 PTY 实现：%s" % sys.platform}))
        return 2
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print(json.dumps({"kind": "error", "message": "缺少 Python Playwright。运行 python3 -m pip install --user playwright 与 python3 -m playwright install chromium"}))
        return 2
    host = Host(opts)

    def stop(_signum, _frame):
        host.closing = "收到终止信号"

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        host.run()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"kind": "error", "message": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False))
        try:
            host.abort()
        finally:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
