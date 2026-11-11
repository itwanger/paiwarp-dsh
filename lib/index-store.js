// Durable session index helpers: one writer per file, temp + atomic rename,
// and recovery from the real per-run manifests when an index is unreadable.
import { mkdir, readFile, readdir, rename, stat, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'

const queues = new Map()

export function atomicWriteJson(path, value) {
  const text = JSON.stringify(value, null, 2) + '\n'
  const previous = queues.get(path) || Promise.resolve()
  const task = previous.catch(() => {}).then(async () => {
    await mkdir(dirname(path), { recursive: true })
    const temp = join(dirname(path), `.${path.split(sep).pop()}.${process.pid}.${Date.now()}.tmp`)
    await writeFile(temp, text)
    await rename(temp, path)
  })
  queues.set(path, task.catch(() => {}))
  return task
}

export async function readIndex(path) {
  let text
  try {
    text = await readFile(path, 'utf8')
  } catch (error) {
    return error.code === 'ENOENT' ? { missing: true } : { error }
  }
  try {
    const doc = JSON.parse(text)
    if (!doc || !Array.isArray(doc.terminals)) throw new Error('索引缺少 terminals 数组')
    return { doc }
  } catch (error) {
    return { error: new Error('索引 JSON 无效：' + error.message) }
  }
}

async function count(dir, pattern) {
  try {
    return (await readdir(dir)).filter(name => pattern.test(name)).length
  } catch {
    return 0
  }
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'))
  } catch {
    return undefined
  }
}

// Rebuild the index from every run's own manifest and its persisted terminal
// state. Nothing is invented: a pair is kept only when terminal id and run id
// agree across run.json and <terminal>.json.
export async function recoverIndex(root, liveDir) {
  const runsDir = join(root, '.paiwarp', 'runs')
  let entries = []
  try {
    entries = await readdir(runsDir, { withFileTypes: true })
  } catch {
    return { doc: undefined, entries: [] }
  }
  const terminals = []
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    const runDir = join(runsDir, entry.name)
    const manifest = await readJson(join(runDir, 'run.json'))
    if (!manifest || typeof manifest.terminal !== 'string' || !/^t\d+$/.test(manifest.terminal)) continue
    const expectedRun = manifest.run ? resolve(root, manifest.run) : undefined
    if (expectedRun && expectedRun !== resolve(runDir)) continue
    const state = liveDir ? await readJson(join(liveDir, manifest.terminal + '.json')) : undefined
    if (liveDir) {
      if (!state || state.terminal !== manifest.terminal) continue
      const stateRun = state.run || ''
      if (stateRun && stateRun !== manifest.run && stateRun !== entry.name) continue
    }
    const info = await stat(runDir).catch(() => undefined)
    const report = await readJson(join(runDir, 'checks.json'))
    terminals.push({
      terminal: manifest.terminal,
      title: manifest.title || manifest.terminal,
      run: relative(root, runDir).split(sep).join('/'),
      status: 'exited',
      closed: true,
      paused: false,
      recording: false,
      startedAt: manifest.startedAt || info?.birthtime?.toISOString?.() || undefined,
      checks: report?.results?.length || 0,
      assets: (await count(join(runDir, 'screenshots'), /\.(png|jpe?g|webp|gif)$/i))
        + (await count(join(runDir, 'video'), /\.(mp4|webm)$/i)),
      recovered: true,
    })
  }
  if (!terminals.length) return { doc: undefined, entries: [] }
  terminals.sort((a, b) => Number(a.terminal.slice(1)) - Number(b.terminal.slice(1)))
  return {
    doc: {
      version: 1,
      workspace: root,
      updatedAt: new Date().toISOString(),
      recovered: true,
      recoveredAt: new Date().toISOString(),
      terminals,
    },
    entries: terminals,
  }
}

export function maxTerminalId(terminals) {
  return terminals.reduce((max, item) => {
    const match = /^t(\d+)$/.exec(String(item.terminal || ''))
    return match ? Math.max(max, Number(match[1])) : max
  }, 0)
}
