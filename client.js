window.__ModuleLoader__.load({
  id: 'paiwarp-dsh',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const opened = new Set()
    const label = '/paiwarp '

    const chip = (extra = {}) => ({
      font: 'inherit', border: '1px solid var(--dsw-alias-border-l1)', borderRadius: 6,
      padding: '4px 9px', color: 'var(--dsw-alias-label-primary)', background: 'transparent',
      cursor: 'pointer', ...extra
    })

    function ToolCard({phase, callId, open}) {
      React.useEffect(() => {
        if (phase === 'start' && !opened.has(callId)) { opened.add(callId); open() }
      }, [callId, phase])
      return h('button', {style: chip(), onClick: open}, 'PaiWarp · 查看本机终端')
    }

    function mediaType(path) {
      const ext = (String(path).toLowerCase().match(/\.([a-z0-9]+)$/) || [])[1] || ''
      if (ext === 'mp4') return 'video/mp4'
      if (ext === 'webm') return 'video/webm'
      if (ext === 'png') return 'image/png'
      if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg'
      if (ext === 'webp') return 'image/webp'
      if (ext === 'gif') return 'image/gif'
      return 'application/octet-stream'
    }

    // Read one selected asset and release its URL when the preview changes.
    function Media({read, path, label}) {
      const [url, setUrl] = React.useState('')
      const [error, setError] = React.useState('')
      const type = mediaType(path)
      const video = type.startsWith('video/')
      React.useEffect(() => {
        const controller = new AbortController()
        let local
        setUrl(''); setError('')
        read(path, controller.signal).then(bytes => {
          if (controller.signal.aborted) return
          local = URL.createObjectURL(new Blob(bytes, {type}))
          setUrl(local)
        }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
        return () => { controller.abort(); if (local) URL.revokeObjectURL(local) }
      }, [path, read, type])
      if (!url) return h('small', {style: {color: 'var(--dsw-alias-label-secondary)'}}, error || '读取素材…')
      return video
        ? h('video', {src: url, controls: true, style: {width: '100%', borderRadius: 6}})
        : h('img', {src: url, alt: label || 'PaiWarp 素材', style: {width: '100%', borderRadius: 6}})
    }

    function Pane({location, readText, readMedia, list, send}) {
      const [index, setIndex] = React.useState(null)
      const [state, setState] = React.useState(null)
      const [image, setImage] = React.useState('')
      const [error, setError] = React.useState('')
      const [tab, setTab] = React.useState('live')
      const [picked, setPicked] = React.useState('')
      const [input, setInput] = React.useState('')
      const [assets, setAssets] = React.useState([])
      const [checks, setChecks] = React.useState(null)
      const [preview, setPreview] = React.useState('')
      const [assetError, setAssetError] = React.useState('')
      const [indexError, setIndexError] = React.useState('')
      const imageRef = React.useRef('')

      const missingPath = message => /not-found|not found|ENOENT|no entry at|不存在/i.test(String(message || ''))

      React.useEffect(() => {
        const controller = new AbortController()
        let timer
        async function tick() {
          let delay = 900
          try {
            const base = await location
            let doc = null
            let readError = ''
            try { doc = JSON.parse(await readText(base + '/index.json', controller.signal)) } catch (error) {
              if (!missingPath(error.message)) readError = error.message
            }
            if (readError) {
              setIndex(null); setState(null); setIndexError(readError); setError('')
              if (!controller.signal.aborted) timer = setTimeout(tick, 1800)
              return
            }
            setIndexError('')
            if (!doc || !doc.terminals || !doc.terminals.length) {
              setIndex(null); setState(null); setError('')
              if (!controller.signal.aborted) timer = setTimeout(tick, 1800)
              return
            }
            setIndex(doc)
            const active = doc.terminals.find(item => item.terminal === picked) || doc.terminals[doc.terminals.length - 1]
            const next = JSON.parse(await readText(base + '/' + active.terminal + '.json', controller.signal))
            const chunks = await readMedia(base + '/' + active.terminal + '.jpg', controller.signal)
            if (controller.signal.aborted) return
            const url = URL.createObjectURL(new Blob(chunks, {type: 'image/jpeg'}))
            setImage(url)
            if (imageRef.current) URL.revokeObjectURL(imageRef.current)
            imageRef.current = url
            setState(next)
            setError('')
            if (next.status === 'exited') delay = 2500
          } catch (e) {
            if (!controller.signal.aborted) setError(e.message)
          }
          if (!controller.signal.aborted) timer = setTimeout(tick, delay)
        }
        tick()
        return () => {
          controller.abort()
          clearTimeout(timer)
          if (imageRef.current) { URL.revokeObjectURL(imageRef.current); imageRef.current = '' }
        }
      }, [location, picked])

      // The index is authoritative (workspace-relative run directory); older
      // persisted terminal state only carried the run id, so normalize that.
      const term = index && state
        ? index.terminals.find(item => item.terminal === state.terminal) || index.terminals[0]
        : null
      const rawRun = (term && term.run) || (state && state.run) || ''
      const run = rawRun && !rawRun.includes('/') && !rawRun.startsWith('/')
        ? '.paiwarp/runs/' + rawRun
        : rawRun

      React.useEffect(() => {
        setAssets([]); setChecks(null); setPreview(''); setAssetError('')
      }, [run])

      React.useEffect(() => {
        if (tab !== 'assets' || !run) return
        const controller = new AbortController()
        let timer
        const notFound = missingPath
        async function load() {
          const found = []
          let failure = ''
          for (const [dir, kind] of [[run + '/screenshots', 'image'], [run + '/video', 'video']]) {
            try {
              const page = await list(dir, controller.signal)
              for (const entry of page.entries || []) {
                if (entry.type === 'file' && /\.(png|jpe?g|webp|gif|mp4|webm)$/i.test(entry.name)) {
                  found.push({kind, path: dir + '/' + entry.name, name: entry.name})
                }
              }
            } catch (error) {
              if (!notFound(error.message)) failure = error.message
            }
          }
          let report = null
          try {
            report = JSON.parse(await readText(run + '/checks.json', controller.signal))
          } catch (error) {
            if (!notFound(error.message)) failure = failure || error.message
          }
          if (controller.signal.aborted) return
          found.sort((a, b) => a.name.localeCompare(b.name))
          setAssets(found)
          setChecks(report)
          setAssetError(failure)
          setPreview(current => current && !found.some(item => item.path === current) ? '' : current)
          timer = setTimeout(load, 2000)
        }
        load()
        return () => { controller.abort(); clearTimeout(timer) }
      }, [tab, run, list, readText])

      // Every manual action names the terminal currently shown, so two
      // terminals never act on each other's target.
      const act = async payload => {
        if (!state) return
        try {
          await send('act ' + JSON.stringify({terminal: state.terminal, ...payload}))
          setError('')
        } catch (e) { setError(e.message) }
      }
      const button = (text, click, selected) => h('button', {
        type: 'button', key: text, onClick: click, 'aria-pressed': selected,
        style: chip(selected ? {background: 'var(--dsw-alias-bg-layer-2)', borderColor: 'var(--dsw-alias-brand-primary)'} : {})
      }, text)
      const row = {display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap'}
      const muted = {color: 'var(--dsw-alias-label-secondary)', fontSize: 12}
      const status = state ? (state.status === 'exited' ? '已退出' : state.paused ? '已接管' : '运行中') : '等待终端'
      const seconds = state && state.recording && state.recordStartedAt
        ? Math.max(0, Math.round(Date.now() / 1000 - state.recordStartedAt)) : 0

      return h('section', {style: {padding: 12, display: 'grid', gap: 10, alignContent: 'start'}},
        h('div', {style: {display: 'flex', gap: 8, alignItems: 'baseline'}},
          h('strong', null, 'PaiWarp'),
          h('span', {style: muted}, index ? index.workspace : '本机真实终端')),
        h('div', {style: {...row, justifyContent: 'space-between'}},
          h('div', {style: row},
            h('span', {style: {fontSize: 12, color: state && state.paused ? 'var(--dsw-alias-state-warn-primary)' : 'var(--dsw-alias-state-success-primary)'}}, status),
            state && h('span', {style: muted}, state.terminal),
            state && h('span', {style: muted}, state.status === 'exited' ? '' : `${state.cols}×${state.rows}`),
            state && state.recording && h('span', {style: muted}, `录制 ${seconds}s`)),
          state && h('span', {style: muted}, run)),
        h('div', {style: row},
          button('终端', () => setTab('live'), tab === 'live'),
          button('素材', () => setTab('assets'), tab === 'assets'),
          index && index.terminals.length > 1 && index.terminals.map(item =>
            button((item.title || item.terminal) + (item.closed ? '（已关闭）' : ''),
              () => setPicked(item.terminal), state && state.terminal === item.terminal))),

        indexError && h('p', {style: {color: 'var(--dsw-alias-state-error-primary)'}},
          `索引读取失败：${indexError}。索引文件可能损坏，请让 Agent 重新打开终端以从运行清单恢复。`),
        !state && !indexError && h('p', {style: muted}, '还没有终端。让 Agent 调用 paiwarp_open，即可在这里看到同一块画面。'),
        state && tab === 'live' && (image
          ? h('img', {src: image, alt: 'PaiWarp 终端实况', style: {width: '100%', background: '#14171c', borderRadius: 6}})
          : h('p', {style: muted}, '等待画面…')),

        state && tab === 'live' && h('div', {style: {...row, justifyContent: 'space-between'}},
          h('div', {style: row},
            state.status === 'exited'
              ? h('span', {style: muted}, '已关闭：仍可查看本次截图和录像')
              : button(state.paused ? '交回 Agent' : '接管键盘', () => act({action: state.paused ? 'resume' : 'pause'})),
            state.status !== 'exited' && button('截图', () => act({action: 'shot'})),
            state.status !== 'exited' && button('停止', () => act({action: 'stop'}))),
          state.exitConfirmed && h('span', {style: muted}, `上条命令退出码 ${state.lastExitCode}`)),

        state && state.paused && state.status !== 'exited' && h('form', {
          onSubmit: event => {
            event.preventDefault()
            const text = input
            setInput('')
            act({action: 'line', text})
          },
          style: row
        },
        h('input', {
          value: input, onChange: event => setInput(event.target.value),
          placeholder: '接管期间由你输入，回车发送', 'aria-label': 'PaiWarp 终端输入',
          style: {flex: '1 1 160px', font: 'inherit', padding: '5px 8px', color: 'var(--dsw-alias-label-primary)',
            background: 'var(--dsw-alias-bg-layer-1)', border: '1px solid var(--dsw-alias-border-l1)', borderRadius: 6}
        }),
        h('button', {type: 'submit', style: chip()}, '发送'),
        ...['esc', 'ctrl+c', 'tab', 'shift+tab', 'up', 'down'].map(key =>
          button(key === 'ctrl+c' ? 'Ctrl+C' : key, () => act({action: 'key', key})))),

        state && tab === 'live' && h('p', {style: muted},
          '接管期间 Agent 写入会被拒绝；交回后 Agent 可以继续操作。'),

        tab === 'assets' && h('div', {style: {display: 'grid', gap: 8}},
          assetError && h('p', {style: {color: 'var(--dsw-alias-state-error-primary)'}}, `读取素材失败：${assetError}`),
          !assets.length && !assetError && h('p', {style: muted}, '本次运行还没有截图或录像。'),
          h('div', {style: row}, ...assets.map(item =>
            button(`${item.kind === 'video' ? '▶' : '图'} ${item.name}`, () => setPreview(item.path), preview === item.path))),
          preview && h(Media, {read: readMedia, path: preview, label: preview}),
          checks && h('div', {style: {fontSize: 12}},
            h('strong', null, `检查结果：${checks.verdict}`),
            h('ul', {style: {paddingLeft: 18, margin: '6px 0'}},
              ...(checks.results || []).map((item, index) =>
                h('li', {key: index, style: {color: item.verdict === 'failed' ? 'var(--dsw-alias-state-error-primary)' : 'inherit'}},
                  `${item.verdict === 'passed' ? '通过' : item.verdict === 'failed' ? '失败' : '未验证'} · ${item.id}：${item.detail || ''}`)))),
          checks && h('p', {style: muted}, checks.limitation || '')),

        error && h('small', {style: {color: 'var(--dsw-alias-state-error-primary)'}}, error))
    }

    return {
      inject: ['slots', 'sidebarRight', 'sidebarRightTabs', 'remote', 'remote.commands', 'remote.workspaceFiles'],
      apply(ctx) {
        ctx.effect(() => ctx.sidebarRightTabs.register({
          id: 'paiwarp-dsh',
          kind: 'paiwarp',
          multiple: false,
          priority: 'builtin',
          title: () => 'PaiWarp',
          guide: [{id: 'open', order: 21, title: () => 'PaiWarp', description: () => '本机真实终端与实测素材'}]
        }), 'paiwarp.tab')
        ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
          name: 'tool.call.toolview', key: 'paiwarp_open',
          inject: () => ({open: () => ctx.sidebarRight.openTab('paiwarp')})
        }, ToolCard))
        ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({
          name: 'sidebar.right.pane.tab', key: 'paiwarp-dsh',
          inject: sessionId => {
            const unwrap = result => {
              if (!result.ok) throw new Error(result.error?.message || '读取失败')
              return result.value
            }
            const base = crypto.subtle.digest('SHA-256', new TextEncoder().encode(sessionId)).then(hash =>
              '.paiwarp/live/' + Array.from(new Uint8Array(hash).slice(0, 16), n => n.toString(16).padStart(2, '0')).join(''))
            return {
              location: base,
              send: async command => {
                const value = unwrap(await ctx.remote.commands.execute(sessionId, label + command, []))
                if (value?.result?.kind !== 'success') throw new Error(value?.result?.text || '终端不可用')
              },
              readText: async (path, signal) => unwrap(await ctx.remote.workspaceFiles.read(sessionId, path, {}, signal)).text,
              list: async (path, signal) => unwrap(await ctx.remote.workspaceFiles.list(sessionId, path, signal)),
              readMedia: async (path, signal) => {
                const chunks = []
                for (let offset = 0; ;) {
                  const page = unwrap(await ctx.remote.workspaceFiles.readBytes(sessionId, path,
                    {range: {offset, length: 512 * 1024}}, signal))
                  chunks.push(page.data)
                  if (page.eof) return chunks
                  if (!page.data.length) throw new Error('素材读取中断')
                  offset += page.data.length
                }
              }
            }
          }
        }, Pane))
      }
    }
  }
})
