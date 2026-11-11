import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { planReplacement, replaceImages } from '../lib/replace-images.js'

const ARTICLE = [
  '# 教程',
  '正文第一段，正文里也提到 a.png 这个词。',
  '![启动画面](https://cdn.example.com/a.png)',
  '',
  '```sh',
  'mvn clean package',
  '```',
  '![编译](https://cdn.example.com/a.png)',
  '',
  '普通链接：[文档](https://cdn.example.com/doc.png)',
].join('\n')

async function tempDir(prefix = 'paiwarp-img-') {
  return mkdtemp(join(tmpdir(), prefix))
}

test('只替换独占一行图片的地址，其他内容逐字节保留', () => {
  const plan = planReplacement(Buffer.from(ARTICLE), [
    { from: 'https://cdn.example.com/a.png', to: './assets/a.png', expect: 2 },
  ])
  const after = plan.updated.toString()
  assert.equal(after.split('./assets/a.png').length - 1, 2)
  assert.equal(after.replaceAll('./assets/a.png', 'https://cdn.example.com/a.png'), ARTICLE)
})

test('正文词语不能被当成图片地址', () => {
  assert.throws(() => planReplacement(Buffer.from(ARTICLE), [
    { from: 'a.png', to: 'b.png' },
  ]), /不是独占一行的图片地址/)
})

test('普通链接不能被当成图片地址', () => {
  assert.throws(() => planReplacement(Buffer.from(ARTICLE), [
    { from: 'https://cdn.example.com/doc.png', to: 'x.png' },
  ]), /不是独占一行的图片地址/)
})

test('围栏代码块里的伪图片不参与，伪关闭行不算关闭', () => {
  const text = [
    '```md',
    '```not-a-close',
    '![a](old.png)',
    '```',
    '',
  ].join('\n')
  assert.throws(() => planReplacement(Buffer.from(text), [
    { from: 'old.png', to: 'new.png' },
  ]), /不是独占一行的图片地址/)
})

test('HTML 注释里的伪图片不参与', () => {
  const text = ['<!--', '![a](old.png)', '-->', ''].join('\n')
  assert.throws(() => planReplacement(Buffer.from(text), [
    { from: 'old.png', to: 'new.png' },
  ]), /不是独占一行的图片地址/)
})

test('图片标题等不支持的写法直接报错', () => {
  const text = '![a](old.png "标题")\n'
  assert.throws(() => planReplacement(Buffer.from(text), [
    { from: 'old.png', to: 'new.png' },
  ]), /不是独占一行的内联图片/)
})

test('新地址不能破坏 Markdown 结构', () => {
  const text = '![a](old.png)\n'
  for (const bad of ['a b.png', 'a\nb.png', 'a(b.png', 'a<b.png', '#anchor']) {
    assert.throws(() => planReplacement(Buffer.from(text), [
      { from: 'old.png', to: bad },
    ]))
  }
})

test('出现次数不符时拒绝', () => {
  assert.throws(() => planReplacement(Buffer.from(ARTICLE), [
    { from: 'https://cdn.example.com/a.png', to: 'x.png', expect: 1 },
  ]), /出现 2 次/)
})

test('非 UTF-8 文件拒绝', () => {
  assert.throws(() => planReplacement(Buffer.from([0xff, 0xfe, 0x00]), [
    { from: 'a', to: 'b' },
  ]), /UTF-8/)
})

test('方案不落盘，apply 必须带预览的 sha256', async () => {
  const dir = await tempDir()
  try {
    await writeFile(join(dir, 'tutorial.md'), ARTICLE)
    const plan = await replaceImages({
      root: dir, file: 'tutorial.md', apply: false,
      replacements: [{ from: 'https://cdn.example.com/a.png', to: 'https://cdn.example.com/b.png', expect: 2 }],
    })
    assert.equal(plan.applied, false)
    assert.equal(await readFile(join(dir, 'tutorial.md'), 'utf8'), ARTICLE)
    await assert.rejects(replaceImages({
      root: dir, file: 'tutorial.md', apply: true,
      replacements: [{ from: 'https://cdn.example.com/a.png', to: 'https://cdn.example.com/b.png', expect: 2 }],
    }), /sha256/)
    const written = await replaceImages({
      root: dir, file: 'tutorial.md', apply: true, expectSha256: plan.before.sha256,
      replacements: [{ from: 'https://cdn.example.com/a.png', to: 'https://cdn.example.com/b.png', expect: 2 }],
    })
    assert.equal(written.applied, true)
    assert.equal(await readFile(join(dir, 'tutorial.md'), 'utf8'),
      ARTICLE.replaceAll('https://cdn.example.com/a.png', 'https://cdn.example.com/b.png'))
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('预览之后文件被修改就拒绝写回', async () => {
  const dir = await tempDir()
  try {
    const file = join(dir, 'tutorial.md')
    await writeFile(file, ARTICLE)
    const replacement = [{ from: 'https://cdn.example.com/a.png', to: 'https://cdn.example.com/b.png', expect: 2 }]
    const plan = await replaceImages({ root: dir, file: 'tutorial.md', apply: false, replacements: replacement })
    await writeFile(file, ARTICLE + '\n作者补了一句。\n')
    await assert.rejects(replaceImages({
      root: dir, file: 'tutorial.md', apply: true, expectSha256: plan.before.sha256, replacements: replacement,
    }), /预览之后/)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('符号链接指向工作区外时拒绝', async () => {
  const root = await tempDir()
  const outside = await tempDir()
  try {
    await writeFile(join(outside, 'tutorial.md'), ARTICLE)
    await symlink(join(outside, 'tutorial.md'), join(root, 'link.md'))
    await assert.rejects(replaceImages({
      root, file: 'link.md', apply: false,
      replacements: [{ from: 'https://cdn.example.com/a.png', to: 'b.png', expect: 2 }],
    }), /工作区/)
  } finally {
    await rm(root, { recursive: true, force: true })
    await rm(outside, { recursive: true, force: true })
  }
})

test('拒绝工作区外的普通路径', async () => {
  const dir = await tempDir()
  try {
    await mkdir(join(dir, 'inner'))
    await writeFile(join(dir, 'outside.md'), 'a')
    await assert.rejects(replaceImages({
      root: join(dir, 'inner'), file: '../outside.md', apply: false,
      replacements: [{ from: 'a', to: 'b' }],
    }), /工作区/)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})
