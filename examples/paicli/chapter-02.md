# PaiCLI 第二章：计划模式与 DAG

对应教程 `docs/articles/build-agent-p2-plan-execute.md` 的「09、跑起来看看」。

## 目标

证明串行计划、可并行 DAG、按 `I` 修改计划、`Shift+Tab` 后的 plan 模式和 `/exit` 都由真实 PaiCLI 执行，并且计划里声明的依赖真的决定了并行和结果传递。

## 准备

先完成[本目录准备说明](README.md)，在仓库根目录构建，再在独立实验目录运行复制后的 jar。下列 jar 路径需要替换为实际路径。

## 步骤

1. `paiwarp_open`，`record: true`，标题写“第二章”。
2. `mvn clean package`，等退出码 0。
3. 启动 `java -Duser.home="<临时目录>" -jar target/paicli-1.0-SNAPSHOT.jar`，等启动画面。
4. 原样输入：`/plan 创建一个 Java 项目叫 demo，写一个 Hello 类输出 Hello World，然后编译运行`，审阅计划时截图 `serial-plan`，然后回车执行。
5. 原样输入教程里的并行 DAG 任务（`/plan 请把任务拆成可并行的 DAG：…`）。截图 `parallel-plan`。检查计划里前四个任务没有互相依赖，最后一个依赖前四个；执行时前四个确实同批推进。
6. 在计划审阅界面按 `I`（`paiwarp_input`，`mode: text`，`text: "I"`），输入补充要求“汇总时用表格输出”，截图 `revised-plan`。检查修改是基于原计划，没有把无关任务全部改写。
7. 按 `Shift+Tab` 切换到 plan 模式，直接输入一条普通任务（例如“读取 pom.xml 前 20 行”），确认它仍然先出计划。截图 `plan-mode-task`。
8. 输入 `/exit`，等回到 shell，`paiwarp_close`。

## 核对

- 计划任务数、依赖关系、并行批次要与教程描述一致；不一致时报告实际计划，不要说“通过”。
- 串行示例里，后一步确实使用了前一步的结果（例如编译的是刚创建的项目）。
- 修改计划后，`I` 补充的要求出现在新计划里，原有任务 id 和依赖没有被无故清空。
- 文件系统里能看到新项目、编译产物；相关命令的退出码为 0。

## 截图与录屏

截图标签和教程图片一一对应；默认生成本次运行的独立教程副本再换图，不改正式文章。
