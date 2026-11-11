# PaiWarp 接口说明

本文写给后续维护者和想写自己案例的人。实现以 `host.js`、`client.js`、`lib/terminal_host.py` 为准。

## 工具

所有工具返回一个 JSON 字符串。`terminal` 省略时使用本会话最近一个仍在运行的终端。

### paiwarp_open

```json
{"shell": "/bin/bash", "cols": 100, "rows": 31, "record": false, "title": "构建"}
```

返回 `terminal`、`run`、`workspace`、`shell`、`cols`、`rows`、`viewWidth`、`viewHeight`、`screenWidth`、`screenHeight`、`status`、`revision`、`seq`、`cursor`、`screen`、`exitTracking`、`keyMap`。视口按 xterm 实际渲染尺寸放大，末尾行列不会被裁掉。`seq` 是输入序号，与屏幕 `revision` 分开。

### paiwarp_read

```json
{"terminal": "t1", "since": 1234}
```

返回同一份状态和 `output`（`since` 之后的增量，最多 8000 字符，`truncated` 标明是否截断）。`cursor` 是下一次 `since`。

### paiwarp_input

```json
{"terminal": "t1", "seq": 0, "mode": "line", "text": "mvn clean package"}
```

- `mode=text` 只键入；`line` 键入并回车；`paste` 多行粘贴（终端启用 bracketed paste 时带上标记）；`key` 发送一个按键。
- 录制期间调用 `resize` 会被拒绝，避免视频尺寸和画面不一致。
- `key` 的名字：`enter`、`return`、`tab`、`shift+tab`、`esc`、`escape`、`backspace`、`ctrl+c`、`ctrl+d`、`ctrl+l`、`ctrl+o`、`ctrl+z`、`delete`、`up`、`down`、`left`、`right`、`home`、`end`、`pageup`、`pagedown`、`space`。
- 接受输入前先递增内部 `seq`，写入串行化；`seq` 不匹配直接拒绝，且不会写入。错误信息里带当前状态，照着重新读即可。
- 用户接管（`paused`）期间 Agent 输入被拒绝；面板手工输入走 `manual` 通道，同样推进 `seq`。

### paiwarp_wait

```json
{"terminal": "t1", "for": "idle", "quietMs": 800, "timeoutMs": 30000}
```

`for` 取 `output`、`idle`、`pattern`、`exit`。超时返回 `timedOut: true` 和现场，不当作成功。取消会中止等待并封存终端。

### paiwarp_capture

```json
{"terminal": "t1", "label": "startup"}
```

返回 `path`（相对工作区）、`bytes`、`width`、`height`（图片真实尺寸）、`screenWidth`、`screenHeight`、`revision`、`at`。截图和录屏使用同一个视口。

### paiwarp_record

```json
{"terminal": "t1", "action": "start"}
{"terminal": "t1", "action": "stop"}
```

停止时返回 `mp4`、`seconds`、`decoded`、`bytes`。没有 ffmpeg 时返回 `webm` 和 `warning`，`mp4` 为 null。

### paiwarp_verify

```json
{"terminal": "t1", "note": "构建结果", "checks": [
  {"id": "class", "kind": "file_exists", "path": "target/classes/App.class"},
  {"id": "exit", "kind": "last_exit_code", "expect": 0}
]}
```

`kind`：

| kind | 需要的字段 | 结论来源 |
|---|---|---|
| `file_exists` | `path` | 工作区内普通文件；符号链接解析到区外则失败 |
| `file_contains` | `path`、`text` | 实际文件字节 |
| `file_matches` | `path`、`pattern` | 实际文件内容 |
| `file_sha256` | `path`、`sha256` | 实际文件内容 |
| `last_exit_code` | `expect` | 受控 Bash 的提示符钩子；其他 shell 标未验证 |
| `exit_code` | `expect` | 终端进程退出码；仍在运行则未验证 |
| `output_matches` | `pattern` | 只报告 `matched`，结论固定为未验证（终端含回显） |

总结论：有 `failed` 就是 `failed`；否则有 `unverified` 就是 `unverified`；全部通过才是 `passed`。至少一个检查项，空列表直接拒绝。

### paiwarp_replace_images

```json
{"file": "docs/tutorial.md", "replacements": [{"from": "https://old/a.png", "to": "./img/a.png"}], "apply": false}
```

- 只认独占一行的 `![alt](地址)`；围栏代码块和缩进代码块里的伪图片不参与；其他图片写法直接报错。
- `from` 必须是某个图片地址本身，不能是正文词语或普通链接。
- `apply=false` 返回 `before.sha256` 和每个地址的字节偏移。
- `apply=true` 必须带同一个 `sha256`；文件在预览后变化就拒绝写入。写入后重新校验摘要。
- 目标文件若是符号链接，解析后必须仍在本工作区内。

### paiwarp_close

结束进程树、封存录屏、写清单；确认进程真正退出后才返回 `status: "closed"`。关闭的终端保留在索引里供面板看素材。

## 终端宿主协议

`lib/terminal_host.py` 是独立进程，stdin/stdout 用一行一个 JSON：

```json
{"id": 7, "action": "input", "kind": "line", "data": "ls"}
{"id": 7, "revision": 12, "status": "running", "screen": "...", "seq": 3}
```

- 请求一定带数值 `id`；回复带回同一个 `id`。
- 异步事件不带 `id`，用 `kind` 区分：`ready`、`exit`、`closed`、`warning`、`error`。`ready` 的终端编号字段叫 `terminal`。
- 参数：`--workspace`、`--assets`、`--live`、`--id`、`--run`、`--shell`、`--cols`、`--rows`、`--track-exit`、`--norc`。`--run` 是工作区相对目录，状态里的 `run` 与索引、清单、界面都用这同一个值。

## 文件布局

```
<工作区>/.paiwarp/
  runs/<运行编号>/
    run.json
    events.jsonl
    checks.json
    screenshots/*.png
    video/*.mp4
  live/<会话哈希>/
    index.json
    <终端>.json
    <终端>.jpg
    <终端>.exit        # 受控 Bash 的上一条命令退出码
    last-replacement.json
```

`index.json` 保留已关闭的终端（`closed: true`），面板据此继续展示素材。每次写入同一个 `index.json` 会按路径串行、先写临时文件再原子改名；会话结束只关闭进程，不清空索引。索引损坏时，宿主会从各运行目录的 `run.json` 和 `<终端>.json` 重新生成，并在文件里标 `recovered: true`，旧记录只能查看，不能输入。`index.json`、`run.json`、`<终端>.json` 里的 `run` 都是工作区相对路径（例如 `.paiwarp/runs/<运行编号>`）；早期只写裸编号的状态仍可借索引里的相对路径展示。

素材页每 2 秒刷新一次，新截图/录像会出现；切换终端会清掉旧预览；目录读不到时显示真实错误。素材支持 PNG/JPEG/WebP/GIF、MP4 和 WebM，WebM 按 `video/webm` 播放。

`run.json` 也使用同样的原子写入。它记录实际工作目录、shell、权限模式（`permission.pty: "host"`）、开始/结束时间、退出码、截图/录像列表和最后的诊断信息。

## 权限

打开前按 `ctx.sandboxPolicy` 的当前模式检查：非 `danger-full-access` 通过 `ctx.get('approval')` 申请一次；每次后续操作重新核对，模式变化会封存终端。终端进程以当前用户权限运行，不经过命令沙箱。


## 桌面命令

面板通过 `/paiwarp act <JSON>` 操作当前显示的终端，JSON 形如：

```json
{"terminal": "t1", "action": "pause"}
{"terminal": "t1", "action": "line", "text": "ls -la"}
{"terminal": "t1", "action": "key", "key": "shift+tab"}
```

`action` 支持 `pause`、`resume`、`stop`、`shot`、`line`、`key`。服务端按 `terminal` 检查归属，不会落到另一个终端；已关闭的终端拒绝输入和截图，但素材继续可看。另有 `view`、`list`、`doctor` 三个只读命令。
