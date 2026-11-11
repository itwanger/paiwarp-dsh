# PaiCLI 案例的准备与使用

[PaiCLI](https://github.com/itwanger/paicli) 是被测的 Java Agent 命令行项目，**不是 PaiWarp 运行依赖**。插件通过 `java -jar ...` 启动它，不导入它的 Java 类。

## 准备

1. 另行获取 PaiCLI 仓库，并按它自己的 README 配好 Java 17+、Maven 和模型服务。
2. 在 Harness 中选择 PaiCLI 仓库为工作区，插件仍可安装在别处。
3. 把本目录所需案例复制进这个工作区，例如 `cases/paiwarp/chapter-03.md`。
4. 先读当前版本的教程与实际代码；示例中路径、命令若与当前版本不同，报告差异再调整，不宣称本文件始终适配未来版本。
5. 当前源码只在仓库根目录构建。之后新建独立实验目录，复制构建出的 jar、必要的 demo 输入与配置，在其中运行；Java 使用独立 `-Duser.home` 保存记忆，避免污染个人数据。

不要把密钥打印到终端、截图或报告中。PaiCLI 内层是否会提交实验代码等行为，另由它自身的项目规则约束；请使用专用实验副本。

## 选择章节

| 案例 | 对应教程与目标 |
| --- | --- |
| [第一章](chapter-01.md) | [从零构建 Agent](https://github.com/itwanger/paicli/blob/main/docs/articles/build-agent-from-scratch.md)：编辑、编译与运行 |
| [第二章](chapter-02.md) | [计划与 DAG](https://github.com/itwanger/paicli/blob/main/docs/articles/build-agent-p2-plan-execute.md)：计划执行、依赖与交互审阅；DAG 指任务之间没有环的依赖图 |
| [第三章](chapter-03.md) | [记忆与上下文](https://github.com/itwanger/paicli/blob/main/docs/articles/build-agent-p3-memory.md)：记忆保存、清空后召回与冲突检查 |

在标准模式发：

```text
请先读 cases/paiwarp/chapter-03.md 和当前第三章教程，
用通用 PaiWarp 逐步操作真实终端。每次根据现场决定下一步，
验证实际文件和工具记录，保存截图、完整录像与报告。
只生成换图演示副本，不动正式教程正文。
```

## 不把历史结果当成通过保证

第一、二章专用版本曾跑通过，不等于本次通用版已重新验收所有分支。通用版第三章实际触发过记忆冲突后自行覆盖旧值的失败；运行时必须继续检查旧值是否真的保留。失败时保存材料并明确报告，不恢复数据后重跑挑结果。[完整验证范围](../../docs/validation.md)。
