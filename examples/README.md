# 选择一个示例

Case 是一份含输入、步骤和预期结果的测试案例。这里的文件由 Harness 阅读和执行，不是插件内置的固定脚本。换章节、换语言或换项目不需要修改核心工具。

| 你要做什么 | 从哪里开始 |
| --- | --- |
| 第一次安装，确认终端可用 | [Python 标准库待办程序](python-cli/case.md) |
| 看彩色状态变化、Git 差异、交互式数据检查 | [Color Lab：三个完整案例](color-lab/README.md) |
| 测试自己的项目 | [复制案例模板](case-template.md) |
| 测试 PaiCLI | [准备说明与前三章](paicli/README.md) |

## 最短使用方式

从插件根目录执行以下准备，使用一个尚不存在的新目录：

```sh
mkdir ../paiwarp-demo
cp examples/python-cli/todo.py ../paiwarp-demo/
cp examples/python-cli/case.md ../paiwarp-demo/CASE.md
```

在 Harness 中打开 `paiwarp-demo` 工作区，在标准模式说：

> 请按 CASE.md 用 PaiWarp 完成真实终端测试、结果核对、截图和录屏，结束后关闭本次终端并写报告。

不需要逐个手调工具。需要检查工具行为时，参见[接口说明](../docs/interface.md)。

只换图属于可选任务，必须由用户指定目标文件和对应图片；默认只保存材料。不要把失败现场配到“全部成功”的正文中直接发布。
