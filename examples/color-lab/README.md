# Color Lab · 看得见变化的终端测试

三个可复跑的本地例子，展示 PaiWarp 如何处理彩色输出、交互输入和分阶段取证。用 Python 标准库编写，Git 案例还需要本机 Git；被测程序不调用模型、不联网。外层 Harness 使用你自己的模型配置。

| 案例 | 真实运行内容 | 颜色与截图点 | 独立验证 |
| --- | --- | --- | --- |
| 构建流水线 | 编译、5 项单元测试、ZIP 打包 | 青色就绪 → 测试输出 → 绿色完成 | 进程退出码、ZIP 内容、SHA-256 |
| Git 修复演示 | 3 项测试失败、修改预设缺陷、重新测试 | 红色失败 → 原生红绿 diff → 绿色通过 | 前后退出码、函数内容、差异文件 |
| CSV 控制台 | 逐条输入检查、清理、导出命令 | 黄色待检 → 红色错误行 → 绿色有效行 | 原始 6 行、清理后 4 行、导出总额 412 |

这里的 CSV 是公开演示数据，构建产物是本地示例包。Git 案例由程序修复预设缺陷，不代表 Agent 自主诊断未知缺陷。

## 先准备独立工作区

从插件仓库根目录执行，`paiwarp-color-demo` 必须是新目录：

```sh
mkdir ../paiwarp-color-demo
cp examples/color-lab/*.py ../paiwarp-color-demo/
cp examples/color-lab/CASE.md ../paiwarp-color-demo/
```

在 DeepSeek Harness 桌面添加 `paiwarp-color-demo` 工作区，确认已安装并启用 PaiWarp。无需 Codex、PaiCLI、Java 或 Maven。

## 给 Harness 的提示词

```text
请先读当前工作区 CASE.md，用 PaiWarp 逐条实测全部三个 Color Lab 案例。
每个案例单独打开 Bash 终端，110 列、34 行，从启动开始录制。
出现 CAPTURE 时先截图，再按 Enter；数据控制台根据实际输出继续输入。
不要用批量输入脚本代替逐步操作，不修改程序或预期值来制造通过。
核对真实退出码、文件内容和产物摘要，保存九张关键截图与三段录像。
最后检查录像完整可解码，关闭本次终端和录制进程，写 REPORT.md。
```

本次桌面实际发送的英文短提示词如下，详细步骤由同一份 CASE.md 提供：

```text
Read CASE.md and run all three Color Lab cases step by step with PaiWarp. Verify outputs, take nine screenshots, record three videos, close owned processes and save REPORT.md.
```

也可以只跑其中一组，明确说出案例名。插件提供通用操作工具，CASE.md 负责描述顺序和预期。

## 自己手动体验

在新工作区执行以下任一命令。前两个例子在每个截图点等待 Enter，第三个会显示 `data>` 输入框：

```sh
python3 pipeline.py
python3 git_workbench.py
python3 data_console.py
```

数据控制台的完整顺序为：`scan` → `check` → `export`（应拒绝）→ `repair` → `check` → `export` → `quit`。手动执行本身不会生成 PaiWarp 截图或录像；这些材料由插件保存。

每组结果保存在 `.color-lab/<案例名>/`。再次运行同一组时换新目录，程序拒绝覆盖已有结果。管道输出或设置 `NO_COLOR` 时关闭示例自定义着色；Git diff 明确启用原生颜色。

## 如何判断结果可靠

- 屏幕上的 PASS 来自实际测试进程，但仍要读取 `result.json` 和日志核对。
- Git 第一次退出非 0 是预设负例；修复后同一份测试退出 0 才算整个案例通过。
- CSV 有错误时应阻止导出，不能提前生成 `summary.json`；清理后才允许导出。
- ZIP 摘要要重新计算，CSV 要独立统计，不能仅搜索终端里的“成功”。
- 录像保存成功与完整可解码是两项检查，结束时都要确认。

[逐条测试规范与九个截图点](CASE.md) · [首页画廊](../../README.md#看见状态变化也核对实际结果) · [实测范围与限制](../../docs/validation.md)
