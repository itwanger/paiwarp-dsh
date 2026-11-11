import assert from 'node:assert/strict'
import { mkdtemp, readdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { atomicWriteJson, readIndex } from '../lib/index-store.js'

test('同一路径的并发写入串行落盘，结果始终是完整 JSON', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'paiwarp-index-'))
  try {
    const path = join(dir, 'index.json')
    await Promise.all(Array.from({ length: 20 }, (_, index) =>
      atomicWriteJson(path, { version: 1, terminals: [], round: index })))
    const { doc, error } = await readIndex(path)
    assert.equal(error, undefined)
    assert.equal(doc.version, 1)
    assert.ok(doc.round >= 0 && doc.round < 20)
    const leftovers = (await readdir(dir)).filter(name => name.endsWith('.tmp'))
    assert.deepEqual(leftovers, [])
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})
