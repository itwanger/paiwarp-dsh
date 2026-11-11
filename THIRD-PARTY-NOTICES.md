# 第三方依赖与许可说明

本插件自身以 MIT 许可证发布，见仓库根目录的 `LICENSE`。下面列出的第三方组件保持各自原有许可；本仓库没有改动它们的许可条款，也没有替任何一方重新授权。

## 随包分发的组件

### xterm.js

- 位置：`vendor/xterm/xterm.js`、`vendor/xterm/xterm.css`
- 用途：在隐藏的浏览器页面里实现真实终端渲染；截图和录屏都来自这一份画面。
- 版本：6.0.0（来自 `@xterm/xterm` 包）
- 许可证：MIT
- 版权声明原文见 `vendor/xterm/LICENSE`：
  - Copyright (c) 2017-2019, The xterm.js authors (https://github.com/xtermjs/xterm.js)
  - Copyright (c) 2014-2016, SourceLair Private Company (https://www.sourcelair.com)
  - Copyright (c) 2012-2013, Christopher Jeffrey (https://github.com/chjj/)

## 运行时不随包分发、需要使用者自行安装的组件

### Playwright for Python

- 用途：驱动无头 Chromium，把同一块终端画面渲染成截图和视频。
- 许可证：Apache License 2.0。
- 来源：<https://github.com/microsoft/playwright-python>。
- 本插件不复制、不修改 Playwright 源码，只要求使用者在自己的 Python 环境里安装。

### Playwright 使用的 Chromium 构建

- 用途：实际执行终端页面渲染。
- 许可证：Chromium 项目自身的 BSD 风格许可及其中各组件的许可，随 Chromium 分发文件提供。
- 由 `python3 -m playwright install chromium` 下载，本插件不打包浏览器二进制。

### FFmpeg / ffprobe

- 用途：把 Playwright 录出的 WebM 转成 MP4，并检查能否完整解码。
- 许可证：取决于使用者安装的构建，常见为 LGPL-2.1-or-later 或 GPL；本插件不打包 FFmpeg。
- 未安装时插件保留 WebM 并明确报告 MP4 未生成，不伪装成功。

### Python 标准库

- 用途：PTY、进程控制、JSON 通信等。
- 许可证：Python Software Foundation License，随 Python 解释器提供。

## 示例代码

`examples/` 下的示例（含 Python 标准库小项目）由本仓库编写，同样以 MIT 许可证发布。示例不包含第三方代码。
