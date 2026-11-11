#!/usr/bin/env python3
"""Check the local pieces PaiWarp needs. Never installs or changes anything."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REQUIRED = True


def check(name, ok, detail, required=REQUIRED, hint=None):
    return {"name": name, "ok": bool(ok), "detail": detail, "required": required, "hint": hint}


def run(argv, timeout=20):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return done.returncode, (done.stdout or "").strip(), (done.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, "", str(error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = []
    system = platform.system()
    checks.append(check("平台", system in ("Darwin", "Linux"), system,
                        required=True, hint="第一版只验证 macOS；Linux 需要单独验收，Windows 没有实现"))
    checks.append(check("Python", sys.version.split()[0], sys.executable, required=True,
                        hint="需要 3.9 或更新版本"))
    for name in ("terminal_host.py", "replace-images.js"):
        path = PLUGIN / "lib" / name
        checks.append(check(f"文件 {name}", path.is_file(), str(path)))
    for name in ("xterm.js", "xterm.css", "LICENSE"):
        path = PLUGIN / "vendor" / "xterm" / name
        checks.append(check(f"内置终端渲染 {name}", path.is_file(), str(path),
                            hint="缺少内置 xterm 资源时无法截图或录屏"))
    shell = os.environ.get("SHELL") or "/bin/bash"
    checks.append(check("shell", Path(shell).is_file(), shell,
                        hint="默认取 $SHELL，也可用 PAIWARP_PYTHON / 命令参数覆盖"))

    try:
        import playwright  # noqa: F401
        checks.append(check("Python Playwright", True, getattr(playwright, "__file__", "已安装")))
    except ImportError:
        checks.append(check("Python Playwright", False, "未安装", hint="python3 -m pip install --user playwright"))

    chromium = None
    if checks[-1]["ok"]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as play:
                chromium = play.chromium.executable_path
                browser = play.chromium.launch()
                browser.close()
            checks.append(check("Chromium 启动", True, chromium))
        except Exception as error:
            checks.append(check("Chromium 启动", False, str(error)[:300],
                                hint="python3 -m playwright install chromium"))
    else:
        checks.append(check("Chromium 启动", False, "缺少 Playwright", hint="python3 -m playwright install chromium"))

    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    checks.append(check("ffmpeg", bool(ffmpeg), ffmpeg or "未安装", required=False,
                        hint="没有 ffmpeg 时录屏保留 WebM，不生成 MP4"))
    checks.append(check("ffprobe", bool(ffprobe), ffprobe or "未安装", required=False,
                        hint="没有 ffprobe 时无法核对视频时长"))

    failed = [item for item in checks if item["required"] and not item["ok"]]
    warnings = [item for item in checks if not item["required"] and not item["ok"]]
    report = {
        "ok": not failed,
        "platform": system,
        "plugin": str(PLUGIN),
        "checks": checks,
        "warnings": [item["name"] for item in warnings],
        "notes": "PaiWarp 通过本机 PTY 运行真实程序，不经过命令沙箱；权限仍按 Harness 当前模式检查。",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            mark = "OK " if item["ok"] else ("!! " if item["required"] else "-- ")
            print(f"{mark}{item['name']}: {item['detail']}")
            if not item["ok"] and item["hint"]:
                print("   " + item["hint"])
        print("\n结论：" + ("可以运行" if report["ok"] else "缺少必需组件"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
