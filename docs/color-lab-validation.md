# Color Lab 实测记录

日期：2026-11-11。环境：macOS、DeepSeek Harness 0.2.2-rc.1、DeepSeek-V4.1-Flash。桌面安装的是 PaiWarp 0.2.0；0.2.1 增加文档、示例与素材，终端运行代码未改动。

在独立工作区放入公开的四个 Python 文件及 CASE.md，通过 Harness 桌面标准模式发送[这段提示词](../examples/color-lab/README.md#给-harness-的提示词)。Harness 调用通用 PaiWarp 工具，按现场输出逐次输入、截图、录制和检查。公开示例与实测工作区的 Python 文件逐字节一致。

## 实际结果

| 案例 | 验收结果 | 录像 |
| --- | --- | --- |
| 构建流水线 | compileall 退出 0；5 项 unittest 通过；ZIP 包含源码和测试，514 字节；重新计算摘要匹配 | [18.32 秒 MP4](https://github.com/itwanger/paiwarp-dsh/releases/download/v0.2.1/color-lab-pipeline.mp4) |
| Git 修复演示 | 原函数加法导致 3 项失败、退出 1；改为乘法后相同测试通过、退出 0；差异文件和源码一致 | [15.36 秒 MP4](https://github.com/itwanger/paiwarp-dsh/releases/download/v0.2.1/color-lab-git-workbench.mp4) |
| CSV 交互检查 | 原始 6 行；发现 2 行错误时导出被拒绝；过滤后 4 行有效；导出合计 412.0；原 CSV 保留 | [31.80 秒 MP4](https://github.com/itwanger/paiwarp-dsh/releases/download/v0.2.1/color-lab-data-console.mp4) |

三个被测 Python 程序正常退出，Bash 记录退出码均为 0。Git 程序内部第一次失败是故意设置的负例。程序退出码与关闭交互 Shell 时收到的信号不是同一个值。

九张截图均为 1218 × 804 的 PaiWarp 原始 PNG，覆盖每组的三个阶段；没有重画或把模拟界面当实测截图。三个视频已用 FFmpeg 完整解码，未发现解码错误。它们记录终端程序的运行过程，不是整个 Harness 对话或桌面录屏。

## 截图索引

| 案例 | 第一阶段 | 第二阶段 | 第三阶段 |
| --- | --- | --- | --- |
| 构建 | [准备](images/color-pipeline-01-ready.png) | [测试](images/color-pipeline-02-tests.png) | [产物](images/color-pipeline-03-artifact.png) |
| Git | [失败](images/color-git-01-failing.png) | [差异](images/color-git-02-diff.png) | [通过](images/color-git-03-passing.png) |
| CSV | [待检](images/color-data-01-pending.png) | [无效行](images/color-data-02-invalid.png) | [导出](images/color-data-03-exported.png) |

## 过程中的偏差

Harness 第一次开终端时得到默认 zsh，随后关闭并重新用 Bash 开启。第一次终端未运行案例，没有作为通过证据，也没有将其短录像混入三段案例录像。三个案例之后均只执行一次，没有反复运行后挑选较好的结果。

Git 的错误与修复均由公开示例程序预设，Harness 负责操作终端、等待、取证与核对。本记录不声称 Agent 自主解决了未知代码问题。CSV 同样是公开演示数据，不是线上客户记录。

插件保留原始事件、检查文件和本地 REPORT.md；公开仓库收录截图和可复用代码，视频作为 Release 附件发布。所有本次终端和录制进程在验收后关闭。

[复跑方法](../examples/color-lab/README.md) · [完整步骤](../examples/color-lab/CASE.md) · [插件限制](validation.md)
