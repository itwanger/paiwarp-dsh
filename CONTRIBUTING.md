# 参与开发

## 结构

- `host.js`：Harness 工具、命令、权限、会话隔离和资产清单。
- `client.js`：右侧面板，终端页和素材页，接管按钮。
- `lib/terminal_host.py`：真实 PTY + xterm 页面 + 截图/录屏的独立进程。
- `lib/replace-images.js`：只换图片地址的逐字节替换。
- `lib/doctor.py`：本机依赖检查。
- `examples/`：案例说明，不是运行入口。

## 本地检查

克隆本仓库，按 README 安装 Python 环境、Playwright/Chromium 和 FFmpeg。开发检查需要 Node.js 20+ 与 npm；没有 Node 运行时的普通使用者仍可用 GitHub 运行包安装插件。若使用 `.venv`，先 `source .venv/bin/activate`，确保下面的 `python3` 与子进程使用同一环境。

```sh
python3 lib/doctor.py
node --test tests/replace-images.test.mjs
node --test tests/host_integration.test.mjs   # 用 fake 注册器驱动真实 Python
python3 tests/pty_smoke.py                    # 真实 PTY、粘贴、PNG、MP4、退出码、SIGTERM
node tests/pack-install.mjs                   # npm pack、独立解包、干净环境跑示例
node tests/chapter-artifacts.mjs <运行目录>   # 可选、只读：核对某次已保存的截图和录像
```

默认测试不依赖任何章节实测素材，也不扫描 `.paiwarp/live`；没有第三章的机器同样能全部通过。`chapter-artifacts.mjs` 必须显式给出运行目录，只读列出内容，不参与 `npm test`。

`host_integration.test.mjs` 会真的启动 `/bin/bash`、截图并录一段 MP4，需要本机 Playwright 和 ffmpeg。`pack-install.mjs` 还会用空的 `HOME` 和最小 `PATH` 跑 `examples/python-cli`，确认没有 Codex、PaiCLI 或私人目录依赖。

## 改代码时

- 协议里请求 `id` 和终端编号必须分开；异步事件不能带 `id`。
- 输入防重复用独立的 `seq`，不要拿屏幕 `revision` 当输入序号。
- 任何新操作都要先核对会话权限模式，并在取消时封存终端。
- 新的检查类型必须能说清楚证据来自哪里；终端回显不能单独判通过。
- 新增文件要同步 `package.json` 的 `files` 白名单，再跑一次 `node tests/pack-install.mjs`。

## 打包与发布

1. 更新 `package.json` 版本和 `README.md` 的变更说明。
2. `node tests/pack-install.mjs` 通过后，用 `npm pack --dry-run` 看文件清单。
3. 确认包里没有 `.paiwarp/`、`tests/`、`archive/`、`node_modules/`、`.env`、个人绝对路径和私人运行素材；只包含经过审查的公开演示图。
4. 许可证是 MIT；第三方许可见 `THIRD-PARTY-NOTICES.md`。不要给来源不明的代码补写许可证。
5. 发布由作者手动执行，CI 不自动推送。

## 提交前

- 不要提交真实 API Key、`.env`、运行素材或私人路径。
- 新平台要先实际验收，再改 README 的支持范围。
