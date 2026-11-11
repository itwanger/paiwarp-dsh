// Optional read-only evidence check for one explicit run directory.
// Not part of `npm test`: pass a run directory, e.g.
//   node tests/chapter-artifacts.mjs ../../.paiwarp/runs/<id>
// It lists what the panel should show and never reruns the chapter.
import { readdir, readFile, stat } from 'node:fs/promises'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(dirname(fileURLToPath(import.meta.url)))
const target = process.argv[2]
if (!target) {
  console.error('用法：node tests/chapter-artifacts.mjs <运行目录>')
  process.exit(2)
}
const runDir = isAbsolute(target) ? target : resolve(here, target)
const info = await stat(runDir).catch(() => null)
if (!info || !info.isDirectory()) {
  console.error('运行目录不存在：' + runDir)
  process.exit(1)
}
const list = async sub => {
  try { return (await readdir(join(runDir, sub))).sort() } catch { return [] }
}
const screenshots = await list('screenshots')
const images = screenshots.filter(name => name.toLowerCase().endsWith('.png'))
const videos = (await list('video')).filter(name => /\.(mp4|webm)$/i.test(name))
const checks = await readFile(join(runDir, 'checks.json'), 'utf8').then(JSON.parse).catch(() => null)
console.log('运行目录：' + runDir)
console.log('截图（PNG）：' + images.length + (images.length ? ' -> ' + images.join(', ') : ''))
console.log('录像：' + videos.length + (videos.length ? ' -> ' + videos.join(', ') : ''))
if (checks) console.log('检查报告：' + (checks.verdict || '未知') + '，' + (checks.results || []).length + ' 项')
const ok = images.length + videos.length > 0
console.log(ok ? 'PASS 素材存在，可由桌面素材页展示' : 'FAIL 这个运行目录里没有截图或录像')
process.exit(ok ? 0 : 1)
