# 安装与排错

## 安装来源

推荐克隆 https://github.com/itwanger/paiwarp-dsh 。不需要克隆 PaiCLI，也不需要 Codex。

另一种方式是从 GitHub Releases 下载 `paiwarp-dsh-0.2.0.tgz`：

```sh
mkdir paiwarp-plugin
tar -xzf paiwarp-dsh-0.2.0.tgz -C paiwarp-plugin
cd paiwarp-plugin/package
```

在这个目录按 README 创建 `.venv`、安装 Playwright/Chromium，运行 `lib/doctor.py`；再在 Harness「插件 → 添加插件」填写这个 `package` 目录的绝对路径。

GitHub 的自动 Source code 压缩包是完整源码，包含测试；`.tgz` 是运行包，不带测试目录。二者都能从本地目录安装。运行包和源码都不是 Python 解释器或浏览器安装包。

## Python 环境

插件默认执行桌面进程 PATH 中的 `python3`。`PAIWARP_PYTHON` 可以指定 Python 可执行文件的绝对路径。例如创建 `.venv` 后，实际用的是 `.venv/bin/python`。

macOS 已运行的应用不会因为又执行一次 `open` 就更新进程环境。先结束任务、退出 Harness，再从插件目录执行：

```sh
open -a "DeepSeek Harness" \
  --env "PAIWARP_PYTHON=$PWD/.venv/bin/python" \
  --env "PATH=$PATH"
```

不要使用 `open -n` 强开第二个实例。应用安装名若不同，请替换为实际名称。通过这个命令启动后再启用插件。普通点击 Dock 图标启动时，不保证有同样的环境变量；可把这条启动命令保存到你自己的脚本中复用。

环境检查必须用同一个 Python：

```sh
.venv/bin/python lib/doctor.py --json
```

注意：检查器当前只显示解释器版本，仍需自己确认是 Python 3.9+。FFmpeg、ffprobe 是 PATH 中的可执行文件，不是 pip 包。`PAIWARP_PYTHON` 只选择 Python；shell 通过 `paiwarp_open` 的 `shell` 参数选择，例如 `/bin/bash`。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| `No module named playwright` | 确认 Harness 使用的是安装过 Playwright 的 Python，而非另一个解释器 |
| 找不到 Chromium | 用同一个 `.venv/bin/python -m playwright install chromium` 安装浏览器 |
| 只有 WebM，没有 MP4 | 检查桌面进程能否在 PATH 找到 ffmpeg 和 ffprobe；不要仅检查交互终端 |
| 已安装但没有 PaiWarp 工具 | 确认已启用；升级后等任务结束，完全退出重开；标准模式应有 `paiwarp_open` 等工具 |
| 卸载提示组件仍被其他配置使用 | 结束相关任务并停用组件，退出重开后再卸载旧来源；不要直接删除 Harness 配置文件 |
| 接管后 Agent 不继续 | 点“交回 Agent”，如果对话已有等待卡片，再回答“继续” |
| 过期输入序号被拒绝 | 让 Agent 重新读终端，再使用最新序号；不要关闭防重复检查 |
| 看见 `还没有终端` | 本会话尚未调用 `paiwarp_open`；终端按会话隔离 |
| `索引读取失败` | 保留错误和运行目录，不要删素材；索引恢复能力与限制见 validation.md |
| 退出码未知 | 使用受控 Bash；区分被测程序退出、关闭 shell 的信号以及运行器状态 |

## 升级与卸载

源码安装可在确认没有本地改动后 `git pull --ff-only`，然后结束任务并重启 Harness。运行包安装使用新包解压到新目录，通过插件管理页切换来源；版本和来源都要确认。

卸载先在插件页停用并移除。需要清理磁盘时，自己确认不再需要素材后删除待测项目的 `.paiwarp/`；插件卸载不会自动删除这些证据，也不会卸载共享的 Python、Chromium 或 FFmpeg。
