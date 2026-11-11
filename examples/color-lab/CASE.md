# Color Lab：三组真实彩色终端 Case

三组程序只使用 Python 标准库，第二组还需要本机 Git。它们用 ANSI 控制序列给真实输出着色，是可运行的本地示例，不是生产部署或线上监控模拟。不要将这些人工准备的输入数据称为真实客户数据。

把本目录完整复制到新目录，在 Harness 中将新目录设为工作区。不要在插件源码目录运行。`.color-lab` 已存在时另选新目录，不删除或覆盖以前结果。

请用通用 PaiWarp 逐条操作，不用另一个终端驱动器代替。推荐 Bash、110 列 × 34 行；每组独立终端并从启动开始录像。程序出现 CAPTURE 时先截图，再按 Enter；数据控制台根据实际输出决定下一条命令。

## 1. 构建流水线

启动 `python3 pipeline.py`。

- `pipeline-01-ready`：青色准备完成、黄色等待；截图后 Enter。
- `pipeline-02-tests`：真实 compileall 和 5 项 unittest 的结果；截图后 Enter。
- `pipeline-03-artifact`：绿色完成、实际 zip 字节数和 SHA-256；截图后 Enter 退出。
- 独立核对 `.color-lab/pipeline/result.json` 的两个退出码为 0，zip 存在且摘要匹配。不要只信图里的 PASS。

## 2. Git 红绿差异与失败修复

启动 `python3 git_workbench.py`。程序只初始化一个临时本地 Git 仓库，不提交、不推送、不联网。

- `git-01-failing`：特意准备的加法缺陷使 3 项真实测试失败；红色失败截图后 Enter。
- `git-02-diff`：Git 原生彩色 diff，减号红色、加号绿色；截图后 Enter。
- `git-03-passing`：相同的 3 项测试重新执行并通过；截图后 Enter。
- 核对 beforeExit 非 0、afterExit 为 0，以及 change.diff 与 invoice.py。这个案例是示例程序自身修复预设缺陷，不是宣称 Harness 自主发现并修复未知缺陷。

## 3. CSV 交互控制台

启动 `python3 data_console.py`，先截图 `data-01-pending`。随后逐条输入：

1. `scan`，再 `check`；预期 4 行有效、2 行无效，截图 `data-02-invalid`。
2. `export`；预期被阻止，不能生成 summary.json。
3. `repair`；保留原文件，写 cleaned.csv。再 `check`，预期 4 行通过。
4. `export`；预期 summary.json 为 rows=4、total=412.0。截图 `data-03-exported`。
5. `quit` 正常退出。

独立解析 CSV/JSON，核对原 orders.csv 仍有 6 行、cleaned.csv 为 4 行、summary.json 总额为 412，而不是仅检查屏幕文字。

## 取证与收尾

共 9 张关键截图，3 段终端录像。完成后检查真实退出码，停止并完整验证录像可解码，再关闭本次终端与子进程。写 REPORT.md，列出所有路径、检查结果和失败；不要修改示例程序来伪造通过。无需提交、推送或上传素材。
