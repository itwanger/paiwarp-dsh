// Byte-exact Markdown image replacement. Only a standalone inline image's
// target address may change; prose, links, code, alt text and layout stay put.
import { createHash } from 'node:crypto'
import { lstat, readFile, realpath, rename, unlink, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'

const sha256 = data => createHash('sha256').update(data).digest('hex')
const inside = (base, path) => path === base || path.startsWith(base + sep)

// Only `![alt](address)` occupying one line is supported. Everything else that
// contains an image marker is reported instead of guessed.
export function findImageSlots(text) {
  const lines = text.split('\n')
  const slots = []
  let fence = null
  let comment = false
  let charOffset = 0
  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index].replace(/\r$/, '')
    const lineStart = charOffset
    charOffset += lines[index].length + 1
    if (fence) {
      // Only a bare fence with optional trailing spaces closes the block.
      const close = /^ {0,3}(`{3,}|~{3,})[ \t]*$/.exec(raw)
      if (close && close[1][0] === fence.char && close[1].length >= fence.length) fence = null
      continue
    }
    if (comment) {
      if (raw.includes('-->')) comment = false
      continue
    }
    const opener = /^ {0,3}(`{3,}|~{3,})/.exec(raw)
    if (opener) { fence = { char: opener[1][0], length: opener[1].length }; continue }
    const commentAt = raw.indexOf('<!--')
    if (commentAt !== -1) {
      if (raw.indexOf('-->', commentAt + 4) === -1) comment = true
      continue
    }
    if (!raw.includes('![')) continue
    if (/^(?: {4}|\t)/.test(raw)) continue
    if (!raw.trimStart().startsWith('![')) {
      if (raw.includes('`')) continue
      throw new Error(`第 ${index + 1} 行含行内图片或正文图片，只支持独占一行的内联图片`)
    }
    const match = /^ {0,3}!\[([^\]\r\n]*)\]\(([^()\s]+)\)[ \t]*$/.exec(raw)
    if (!match) {
      throw new Error(`第 ${index + 1} 行不是独占一行的内联图片（不支持图片标题、多张图片或括号地址）`)
    }
    const close = match[0].indexOf('](')
    const prefix = raw.slice(0, close + 2).length
    const address = match[2]
    const startChar = lineStart + prefix
    slots.push({
      line: index + 1,
      alt: match[1],
      address,
      startChar,
      endChar: startChar + address.length,
    })
  }
  return slots
}

function byteOffset(text, charIndex) {
  return Buffer.byteLength(text.slice(0, charIndex), 'utf8')
}

export function assertSafeAddress(address) {
  if (typeof address !== 'string' || !address) throw new Error('新图片地址不能为空')
  if (/[\r\n]/.test(address)) throw new Error('新图片地址不能含换行')
  if (/[\x00-\x1f\x7f]/.test(address)) throw new Error('新图片地址不能含控制字符')
  if (/\s/.test(address)) throw new Error('新图片地址不能含空白')
  if (/[<>`\\]/.test(address)) throw new Error('新图片地址不能含 < > ` 或反斜杠')
  const left = (address.match(/\(/g) || []).length
  const right = (address.match(/\)/g) || []).length
  if (left !== right) throw new Error('新图片地址的括号不配对')
  if (!/^(?:[a-z][a-z0-9+.-]*:|\.{0,2}\/|[A-Za-z0-9_])/i.test(address)) throw new Error('新图片地址格式不受支持')
  if (address.startsWith('#')) throw new Error('新图片地址不能是文档内锚点')
  return address
}

export function planReplacement(buffer, replacements) {
  let text
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    throw new Error('文件不是完整的 UTF-8 文本，拒绝修改')
  }
  if (Buffer.byteLength(text, 'utf8') !== buffer.length) {
    throw new Error('文件不是完整的 UTF-8 文本，拒绝修改')
  }
  const slots = findImageSlots(text)
  const spans = []
  const report = []
  for (const item of replacements) {
    if (!item || typeof item.from !== 'string' || typeof item.to !== 'string' || !item.from || !item.to) {
      throw new Error('每条替换都需要非空的 from 和 to')
    }
    assertSafeAddress(item.to)
    const expect = item.expect === undefined ? 1 : item.expect
    if (!Number.isInteger(expect) || expect < 1) throw new Error('expect 必须是正整数')
    const matches = slots.filter(slot => slot.address === item.from)
    if (matches.length === 0) {
      throw new Error(`“${item.from}”不是独占一行的图片地址，拒绝修改正文或其他链接`)
    }
    if (matches.length !== expect) {
      throw new Error(`“${item.from}”作为图片地址出现 ${matches.length} 次，预期 ${expect} 次，拒绝修改`)
    }
    const to = Buffer.from(item.to, 'utf8')
    const offsets = []
    for (const match of matches) {
      const start = byteOffset(text, match.startChar)
      const length = Buffer.byteLength(match.address, 'utf8')
      spans.push({ offset: start, length, to, line: match.line })
      offsets.push(start)
    }
    report.push({ from: item.from, to: item.to, count: matches.length, offsets })
  }
  spans.sort((a, b) => a.offset - b.offset)
  for (let index = 1; index < spans.length; index += 1) {
    if (spans[index - 1].offset + spans[index - 1].length > spans[index].offset) {
      throw new Error('替换位置重叠，拒绝修改')
    }
  }
  const parts = []
  let cursor = 0
  for (const span of spans) {
    parts.push(buffer.subarray(cursor, span.offset), span.to)
    cursor = span.offset + span.length
  }
  parts.push(buffer.subarray(cursor))
  const updated = Buffer.concat(parts)
  verifyOnlySpansChanged(buffer, updated, spans)
  return { updated, report, spans: spans.length }
}

function verifyOnlySpansChanged(before, after, spans) {
  const expectedLength = before.length + spans.reduce((sum, s) => sum + s.to.length - s.length, 0)
  if (after.length !== expectedLength) throw new Error('替换后长度不符合预期')
  let beforeCursor = 0
  let afterCursor = 0
  for (const span of spans) {
    const gap = span.offset - beforeCursor
    if (!after.subarray(afterCursor, afterCursor + gap).equals(before.subarray(beforeCursor, span.offset))) {
      throw new Error('替换影响了图片地址以外的内容')
    }
    afterCursor += gap + span.to.length
    beforeCursor = span.offset + span.length
  }
  if (!after.subarray(afterCursor).equals(before.subarray(beforeCursor))) {
    throw new Error('替换影响了图片地址以外的内容')
  }
}

async function resolveTarget(base, file) {
  const target = resolve(base, file)
  let info
  try {
    info = await lstat(target)
  } catch {
    throw new Error('文件不存在或不可读')
  }
  if (info.isDirectory()) throw new Error('目标是一个目录')
  const real = await realpath(target)
  if (!inside(base, real)) throw new Error('目标文件（含符号链接）不在当前工作区内')
  if (info.isSymbolicLink() && real === target) throw new Error('符号链接无法解析')
  const realInfo = await lstat(real)
  if (!realInfo.isFile()) throw new Error('目标不是普通文件')
  return { target, real, info: realInfo }
}

export async function replaceImages({ root, file, replacements, apply = false, expectSha256 }) {
  if (!Array.isArray(replacements) || replacements.length === 0) throw new Error('缺少替换项')
  const base = await realpath(root).catch(() => {
    throw new Error('工作区目录不存在或不可读')
  })
  const { target, real, info } = await resolveTarget(base, file)
  const before = await readFile(real)
  const beforeDigest = sha256(before)
  const plan = planReplacement(before, replacements)
  const result = {
    file: relative(base, target),
    applied: false,
    replacements: plan.report,
    bytesChanged: plan.spans,
    before: { sha256: beforeDigest, bytes: before.length, mode: info.mode & 0o777 },
    after: { sha256: sha256(plan.updated), bytes: plan.updated.length },
  }
  if (!apply) return { ...result, note: '仅生成方案，未写入；用户确认后带 sha256 以 apply=true 再次调用' }

  if (typeof expectSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(expectSha256)) {
    throw new Error('apply 需要预览返回的 before.sha256，避免两次调用之间文件被改动')
  }
  const current = await readFile(real)
  if (sha256(current) !== expectSha256) {
    throw new Error('文件在预览之后被修改，已保留原样；请重新生成替换方案')
  }
  if (sha256(current) !== beforeDigest) {
    throw new Error('文件在本次调用内发生变化，已保留原样')
  }
  const temp = join(dirname(real), `.${relative(dirname(real), real)}.paiwarp-${process.pid}-${Date.now()}`)
  await writeFile(temp, plan.updated, { mode: info.mode & 0o777 })
  try {
    const check = await readFile(real)
    if (sha256(check) !== expectSha256) throw new Error('写入前文件被其他人修改，已放弃替换')
    await rename(temp, real)
  } catch (error) {
    await unlink(temp).catch(() => {})
    throw error
  }
  const after = await readFile(real)
  if (sha256(after) !== result.after.sha256) throw new Error('写入后校验不一致，请人工核对')
  return { ...result, applied: true }
}

export async function fileDigest(path) {
  return sha256(await readFile(path))
}
