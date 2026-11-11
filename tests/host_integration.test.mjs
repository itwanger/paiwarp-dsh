import assert from 'node:assert/strict'
import { mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { apply } from '../host.js'

function harness(root) {
  const tools = new Map()
  const commands = new Map()
  const pluginEffects = []
  const agentEffects = []
  const ctx = {
    tools: { register: definition => { tools.set(definition.name, definition); return () => {} } },
    commands: { register: definition => { commands.set(definition.name, definition); return () => {} } },
    systemPrompt: { section: () => () => {} },
    sandboxPolicy: { resolve: () => ({ mode: 'danger-full-access' }) },
    workingDirectory: { ensure: async () => root, get: () => root, defaultDirectory: root },
    get: () => undefined,
    effect: factory => { pluginEffects.push(factory); return () => {} },
  }
  apply(ctx)
  const agent = {
    id: 'sess-integration',
    session: { id: 'sess-integration', header: { cwd: root } },
    ctx: { effect: factory => { const cleanup = factory(); agentEffects.push(cleanup); return cleanup } },
  }
  async function call(name, args = {}, signal) {
    const definition = tools.get(name)
    assert.ok(definition, `工具 ${name} 已注册`)
    const text = await definition.execute(args, {
      agent, callId: 'call-' + name, signal: signal || new AbortController().signal,
    })
    return JSON.parse(text)
  }
  async function command(line) {
    return commands.get('paiwarp').handler({ agent, rawInput: line, signal: new AbortController().signal })
  }
  async function disposeAgent() {
    for (const cleanup of agentEffects.splice(0)) await cleanup?.()
  }
  async function disposePlugin() {
    for (const factory of pluginEffects.splice(0)) {
      const cleanup = factory()
      if (typeof cleanup === 'function') await cleanup()
    }
  }
  async function dispose() {
    await disposeAgent()
    await disposePlugin()
  }
  return { call, command, dispose, disposeAgent, disposePlugin, tools, commands, agent }
}

const pause = ms => new Promise(done => setTimeout(done, ms))

test('真实 Python 终端：打开、输入、等待、截图、录屏、核对、接管、关闭', { timeout: 180000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'paiwarp-host-'))
  const { call, command, dispose } = harness(root)
  let terminal
  try {
    const opened = await call('paiwarp_open', { shell: '/bin/bash', title: '集成测试' })
    terminal = opened.terminal
    assert.equal(opened.status, 'running')
    assert.equal(typeof opened.seq, 'number')
    assert.equal(opened.exitTracking, 'bash-prompt')
    assert.match(opened.run, /^\.paiwarp\/runs\//, '运行目录必须是工作区相对路径')

    let state = await call('paiwarp_read', { terminal })
    assert.equal(state.run, opened.run)
    const badSeq = await call('paiwarp_input', { terminal, seq: state.seq + 9, text: 'true' }).then(
      () => { throw new Error('过期 seq 被接受') }, error => error.message)
    assert.match(badSeq, /seq 已过期/)

    state = await call('paiwarp_input', { terminal, seq: state.seq, mode: 'line', text: "printf 'it-ok\\n'" })
    assert.equal(state.seq, opened.seq + 1)
    for (let index = 0; index < 50; index += 1) {
      state = await call('paiwarp_read', { terminal })
      if (/it-ok/.test(state.screen)) break
      await pause(120)
    }
    assert.match(state.screen, /it-ok/)

    const shot = await call('paiwarp_capture', { terminal, label: 'startup' })
    const image = await readFile(join(root, shot.capture.path))
    assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')

    state = await call('paiwarp_input', { terminal, seq: state.seq, mode: 'line', text: "printf 'abc\\n' > out.txt" })
    await call('paiwarp_wait', { terminal, for: 'idle', timeoutMs: 12000, quietMs: 600 })
    const contents = await readFile(join(root, 'out.txt'), 'utf8')
    const digest = (await import('node:crypto')).createHash('sha256').update(contents).digest('hex')
    const verified = await call('paiwarp_verify', {
      terminal, note: '文件检查',
      checks: [
        { id: 'exists', kind: 'file_exists', path: 'out.txt' },
        { id: 'contains', kind: 'file_contains', path: 'out.txt', text: 'abc' },
        { id: 'regex', kind: 'file_matches', path: 'out.txt', pattern: '^abc' },
        { id: 'digest', kind: 'file_sha256', path: 'out.txt', sha256: digest },
        { id: 'echo', kind: 'output_matches', pattern: 'abc' },
      ],
    })
    assert.equal(verified.verdict, 'unverified')
    assert.equal(verified.results.find(item => item.id === 'echo').verdict, 'unverified')

    await assert.rejects(call('paiwarp_verify', { terminal, checks: [] }), /至少提供一个检查项/)

    const beforeDuplicate = await call('paiwarp_read', { terminal })
    const [firstDup, secondDup] = await Promise.allSettled([
      call('paiwarp_input', { terminal, seq: beforeDuplicate.seq, mode: 'line', text: 'echo first' }),
      call('paiwarp_input', { terminal, seq: beforeDuplicate.seq, mode: 'line', text: 'echo second' }),
    ])
    assert.equal([firstDup, secondDup].filter(item => item.status === 'fulfilled').length, 1)
    state = await call('paiwarp_read', { terminal })

    const outside = await mkdtemp(join(tmpdir(), 'paiwarp-outside-'))
    await writeFile(join(outside, 'secret.txt'), 'outside')
    await symlink(join(outside, 'secret.txt'), join(root, 'escape.txt'))
    const escaped = await call('paiwarp_verify', {
      terminal, checks: [{ id: 'escape', kind: 'file_exists', path: 'escape.txt' }],
    })
    assert.equal(escaped.verdict, 'failed')
    await rm(outside, { recursive: true, force: true })

    state = await call('paiwarp_input', { terminal, seq: state.seq, mode: 'line', text: 'false' })
    let exitState = await call('paiwarp_read', { terminal })
    for (let index = 0; index < 60 && !exitState.exitConfirmed; index += 1) {
      await pause(120)
      exitState = await call('paiwarp_read', { terminal })
    }
    assert.equal(exitState.exitConfirmed, true, '受控 Bash 应给出新的退出码')
    assert.equal(exitState.lastExitCode, 1)
    const exitCheck = await call('paiwarp_verify', {
      terminal, checks: [{ id: 'exit', kind: 'last_exit_code', expect: 1 }],
    })
    assert.equal(exitCheck.verdict, 'passed')

    await call('paiwarp_record', { terminal, action: 'start' })
    await call('paiwarp_input', { terminal, seq: exitState.seq, mode: 'line',
      text: 'for i in 1 2 3; do echo tick-$i; sleep 0.4; done' })
    await pause(400)
    const recorded = await call('paiwarp_record', { terminal, action: 'stop' })
    assert.equal(recorded.decoded, true)
    assert.ok(recorded.seconds > 1)
    const video = await readFile(join(root, recorded.mp4))
    assert.ok(video.length > 1000)

    await command('act ' + JSON.stringify({terminal: terminal, action: 'pause'}))
    const blocked = await call('paiwarp_input', { terminal, seq: (await call('paiwarp_read', { terminal })).seq, text: 'true' })
      .then(() => { throw new Error('接管期间 Agent 仍能输入') }, error => error.message)
    assert.match(blocked, /接管/)
    const manual = await command('act ' + JSON.stringify({terminal: terminal, action: 'line', text: 'echo takeover'}))
    assert.equal(manual.kind, 'success')
    await command('act ' + JSON.stringify({terminal: terminal, action: 'resume'}))
    const afterTakeover = await call('paiwarp_read', { terminal })
    let exiting = await call('paiwarp_input', { terminal, seq: afterTakeover.seq, mode: 'line', text: 'exit 0' })
    for (let index = 0; index < 50 && exiting.status !== 'exited'; index += 1) {
      await pause(120)
      exiting = await call('paiwarp_read', { terminal })
    }
    assert.equal(exiting.status, 'exited')
    const closed = await call('paiwarp_close', { terminal })
    assert.equal(closed.status, 'closed')
    assert.equal(closed.exitCode, 0)
    assert.equal(closed.verified, true)
    const runDir = join(root, closed.run)
    const manifest = JSON.parse(await readFile(join(runDir, 'run.json'), 'utf8'))
    assert.equal(manifest.exitCode, 0)
    assert.equal(manifest.permission.pty, 'host')
    const events = (await readFile(join(runDir, 'events.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line))
    const inputs = events.filter(event => event.event === 'input')
    assert.ok(inputs.length >= 4)
    const order = events.map(event => event.event)
    assert.ok(order.indexOf('open') < order.indexOf('input'))
    assert.ok(order.indexOf('input') < order.indexOf('verify'))
    assert.ok(order.includes('closed') || order.includes('shutdown'))
    const files = await readdir(join(runDir, 'screenshots'))
    assert.ok(files.some(name => name.endsWith('.png')))
    terminal = undefined
  } finally {
    if (terminal) await call('paiwarp_close', { terminal }).catch(() => {})
    await dispose()
    await rm(root, { recursive: true, force: true })
  }
})

test('取消等待会封存终端并确认进程退出', { timeout: 120000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'paiwarp-abort-'))
  const { call, dispose } = harness(root)
  let terminal
  try {
    const opened = await call('paiwarp_open', { shell: '/bin/bash' })
    terminal = opened.terminal
    const pid = opened.pid
    assert.ok(pid > 0, '需要真实 shell 进程号')
    await pause(500)
    const controller = new AbortController()
    const waiting = call('paiwarp_wait', { terminal, for: 'exit', timeoutMs: 60000 }, controller.signal)
    await pause(250)
    controller.abort()
    await assert.rejects(waiting, /已取消/)
    await pause(1500)
    const closed = await call('paiwarp_close', { terminal })
    assert.equal(closed.status, 'closed')
    assert.equal(closed.verified, true)
    assert.equal(closed.run, opened.run)
    let alive = true
    try { process.kill(pid, 0) } catch { alive = false }
    assert.equal(alive, false, `shell 进程 ${pid} 仍在运行`)
    terminal = undefined
  } finally {
    if (terminal) await call('paiwarp_close', { terminal }).catch(() => {})
    await dispose()
    await rm(root, { recursive: true, force: true })
  }
})

test('两个终端交叉动作与关闭后的素材保留', { timeout: 180000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'paiwarp-two-'))
  const { call, command, dispose } = harness(root)
  const terminals = []
  try {
    const first = await call('paiwarp_open', { shell: '/bin/bash', title: '第一个' })
    const second = await call('paiwarp_open', { shell: '/bin/bash', title: '第二个' })
    terminals.push(first.terminal, second.terminal)
    assert.notEqual(first.terminal, second.terminal)

    const paused = await command('act ' + JSON.stringify({ terminal: first.terminal, action: 'pause' }))
    assert.equal(paused.kind, 'success')
    const firstState = await call('paiwarp_read', { terminal: first.terminal })
    const secondState = await call('paiwarp_read', { terminal: second.terminal })
    assert.equal(firstState.paused, true)
    assert.equal(secondState.paused, false)

    await call('paiwarp_input', { terminal: first.terminal, seq: firstState.seq, mode: 'line', text: 'echo blocked' })
      .then(() => { throw new Error('被接管的终端仍接受 Agent 输入') }, error => assert.match(error.message, /接管/))

    const sent = await command('act ' + JSON.stringify({ terminal: second.terminal, action: 'line', text: "printf 'only-second\\n'" }))
    assert.equal(sent.kind, 'success')
    await pause(600)
    const secondAfter = await call('paiwarp_read', { terminal: second.terminal })
    const firstAfter = await call('paiwarp_read', { terminal: first.terminal })
    assert.match(secondAfter.screen, /only-second/)
    assert.doesNotMatch(firstAfter.screen, /only-second/)

    const closed = await call('paiwarp_close', { terminal: first.terminal })
    assert.equal(closed.status, 'closed')
    const index = JSON.parse(await readFile(
      join(root, '.paiwarp', 'live',
        (await import('node:crypto')).createHash('sha256').update('sess-integration').digest('hex').slice(0, 32),
        'index.json'), 'utf8'))
    const kept = index.terminals.find(item => item.terminal === first.terminal)
    assert.ok(kept, '关闭的终端仍然留在索引里')
    assert.equal(kept.closed, true)
    await readdir(join(root, closed.run, 'screenshots'))

    await call('paiwarp_input', { terminal: first.terminal, seq: 0, mode: 'line', text: 'true' })
      .then(() => { throw new Error('关闭的终端仍接受输入') }, error => assert.match(error.message, /退出|关闭/))

    terminals.length = 0
    await call('paiwarp_close', { terminal: second.terminal })
  } finally {
    for (const terminal of terminals) await call('paiwarp_close', { terminal }).catch(() => {})
    await dispose()
    await rm(root, { recursive: true, force: true })
  }
})

test('owner 清理保留索引，重启后编号递增且旧记录仍可找到', { timeout: 180000 }, async () => {
  const { createHash } = await import('node:crypto')
  const root = await mkdtemp(join(tmpdir(), 'paiwarp-restart-'))
  const liveDir = join(root, '.paiwarp', 'live',
    createHash('sha256').update('sess-integration').digest('hex').slice(0, 32))
  const indexPath = join(liveDir, 'index.json')
  const readDoc = async () => JSON.parse(await readFile(indexPath, 'utf8'))
  const first = harness(root)
  let second, third
  try {
    const a = await first.call('paiwarp_open', { shell: '/bin/bash', title: 'a' })
    const b = await first.call('paiwarp_open', { shell: '/bin/bash', title: 'b' })
    assert.deepEqual([a.terminal, b.terminal], ['t1', 't2'])
    await first.call('paiwarp_close', { terminal: a.terminal })
    await first.call('paiwarp_close', { terminal: b.terminal })
    assert.equal((await readDoc()).terminals.length, 2)

    await first.disposeAgent()
    const afterDispose = await readDoc()
    assert.deepEqual(afterDispose.terminals.map(item => item.terminal).sort(), ['t1', 't2'])
    for (const item of afterDispose.terminals) {
      assert.equal(item.closed, true)
      await readFile(join(root, item.run, 'run.json'), 'utf8')
    }

    second = harness(root)
    const c = await second.call('paiwarp_open', { shell: '/bin/bash', title: 'c' })
    assert.equal(c.terminal, 't3', '重启后不能复用旧编号')
    const afterRestart = await readDoc()
    assert.deepEqual(afterRestart.terminals.map(item => item.terminal), ['t1', 't2', 't3'])
    assert.equal(afterRestart.terminals.find(item => item.terminal === 't1').run,
      afterDispose.terminals.find(item => item.terminal === 't1').run)
    await second.call('paiwarp_close', { terminal: c.terminal })
    await second.dispose()

    await writeFile(indexPath, '{"version":1,"terminals":[] ' + '{"terminal":"t1"}')
    third = harness(root)
    const d = await third.call('paiwarp_open', { shell: '/bin/bash', title: 'd' })
    assert.equal(d.terminal, 't4')
    const recovered = await readDoc()
    assert.equal(recovered.recovered, true)
    assert.deepEqual(recovered.terminals.map(item => item.terminal), ['t1', 't2', 't3', 't4'])
    for (const id of ['t1', 't2', 't3']) {
      const item = recovered.terminals.find(entry => entry.terminal === id)
      assert.equal(item.closed, true)
      await readFile(join(root, item.run, 'run.json'), 'utf8')
    }
    await third.call('paiwarp_close', { terminal: d.terminal })
    await third.dispose()
  } finally {
    await first.dispose()
    await second?.dispose()
    await third?.dispose()
    await rm(root, { recursive: true, force: true })
  }
})
