// Pack the plugin, extract it elsewhere, and run the independent checks.
import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdtemp, readdir, readFile, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, extname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(dirname(fileURLToPath(import.meta.url)))
const tests = join(here, 'tests')
const failures = []

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', ...options })
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} 失败\n${result.stdout}\n${result.stderr}`)
  }
  return result.stdout
}

async function walk(dir) {
  const found = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) found.push(...await walk(path))
    else found.push(path)
  }
  return found
}

const root = await mkdtemp(join(tmpdir(), 'paiwarp-pack-'))
try {
  const packed = JSON.parse(run('npm', ['pack', '--json', '--pack-destination', root], { cwd: here }))[0]
  const archive = join(root, packed.filename)
  const unpackRoot = join(root, 'unpacked')
  run('mkdir', ['-p', unpackRoot])
  run('tar', ['-xzf', archive, '-C', unpackRoot])
  const unpacked = join(unpackRoot, 'package')
  const files = (await walk(unpacked)).map(path => relative(unpacked, path))

  for (const required of ['host.js', 'client.js', 'terminal.html', 'lib/terminal_host.py',
    'lib/replace-images.js', 'lib/doctor.py', 'vendor/xterm/xterm.js', 'vendor/xterm/xterm.css',
    'examples/paicli/chapter-03.md', 'examples/python-cli/todo.py', 'examples/python-cli/case.md', 'LICENSE',
    'THIRD-PARTY-NOTICES.md', 'README.md', 'docs/interface.md', 'locale/zh.json', 'icon.svg']) {
    assert.ok(files.includes(required), `发布包缺少 ${required}`)
  }
  for (const forbidden of ['archive', 'tests', 'node_modules', '.env', '__pycache__', 'run.py', 'chapter.py', 'terminal.py']) {
    assert.ok(!files.some(path => path === forbidden || path.startsWith(forbidden + '/')),
      `发布包不应包含 ${forbidden}`)
  }
  assert.ok(!files.some(path => /(^|\/)\.paiwarp\//.test(path)), '发布包不应包含运行素材')

  const doctor = JSON.parse(run('python3', ['lib/doctor.py', '--json'], { cwd: unpacked }))
  assert.equal(doctor.ok, true, JSON.stringify(doctor))

  const smoke = run('python3', [join(tests, 'pty_smoke.py'), '--plugin', unpacked])
  assert.match(smoke, /PASS real PTY/)
  const demo = run('python3', [join(tests, 'demo_clean_env.py'), '--plugin', unpacked])
  assert.match(demo, /PASS clean env demo/)

  const own = files.filter(path => /^(host\.js|client\.js|lib\/.*\.(py|js)|docs\/.*\.md|examples\/.*|README\.md|CONTRIBUTING\.md|package\.json)$/.test(path))
  for (const path of own) {
    const text = await readFile(join(unpacked, path), 'utf8')
    assert.ok(!text.includes('/Users/itwanger'), `${path} 含个人绝对路径`)
    assert.ok(!/(DEEPSEEK_API_KEY|GLM_API_KEY|HUNYUAN_API_KEY)=/.test(text), `${path} 含密钥样式`)
  }
  const total = (await Promise.all(files.map(async path => (await stat(join(unpacked, path))).size)))
    .reduce((sum, size) => sum + size, 0)
  console.log(`PASS pack: ${packed.filename}，${files.length} 个文件，${(total / 1024).toFixed(0)} KiB；独立安装、doctor、真实 PTY、干净环境示例均通过`)
} catch (error) {
  failures.push(error.message)
  console.error('FAIL', error.message)
  process.exitCode = 1
} finally {
  if (process.exitCode) console.error('保留打包目录：' + root)
  else await rm(root, { recursive: true, force: true })
}
