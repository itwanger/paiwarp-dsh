# PaiCLI 第一章：跑起来看看

对应教程 `docs/articles/build-agent-from-scratch.md` 的「07、跑起来看看」。

## 目标

用本机真实终端构建并启动 PaiCLI，输入教程里的两条中文任务，证明 PaiCLI 真的调用了工具、改了文件、编译并运行了程序。

## 准备

先看[本目录准备说明](README.md)。需要构建的源码在仓库根目录；要隔离案例文件时，复制必要 demo 和构建后的 jar 到实验目录，使用实际路径启动。

- 当前工作区就是 PaiCLI 仓库根目录。
- 本机有 Java 17+、Maven；模型配置来自 `.env` 或环境变量。不要在报告或截图里打印密钥。
- 在临时 Java 用户目录里运行 PaiCLI，避免影响个人长期记忆；示例代码可以复制到临时目录再改。

## 步骤

1. `paiwarp_open`，`record: true`，标题写“第一章”。
2. 输入 `mvn clean package`，等待退出码 0。构建失败就停下并报告。
3. 启动 `java -Duser.home="<临时目录>" -jar target/paicli-1.0-SNAPSHOT.jar`，等启动画面稳定后截图 `startup`。
4. 原样输入教程第一条任务：`读取 demo/src/main/java/com/example/Hello.java，把输出改成 Hello PaiCLI`，等 PaiCLI 回复结束。
5. 截图 `edit`，然后检查源码里确有 `Hello PaiCLI`，并且本轮 PaiCLI 的会话记录里出现过 `read_file` / `edit_file`（或 `write_file`）调用。会话记录只是这个示例的可选检查，不是插件的核心依赖。
6. 原样输入第二条任务：`进入 demo 目录，编译并运行 Hello.java`，等 PaiCLI 回复结束。
7. 截图 `compile`，核对 `Hello.class` 存在，且 PaiCLI 的 `execute_command` 结果里有退出码 0 和单独一行 `Hello PaiCLI`。
8. 输入 `/exit`，等回到 shell，再 `paiwarp_close`。录屏会转成 MP4。

## 截图与录屏

三张 PNG 和 MP4 默认在 `.paiwarp/runs/<运行编号>/`。教程只替换第 07 节三处原始图片地址时：

1. 先 `paiwarp_replace_images`（`apply: false`）生成方案，确认 `from` 是三处独占一行的图片地址。
2. 用户确认后，带预览返回的 `sha256` 再调用一次，`apply: true`。
3. 正文、代码、alt、图注、空格和换行保持不变；文件在两次调用之间被改过就保留原样并报告。
