// 写路径动作层：组件只调动作，不碰 fetch/轮询。
// 每个动作 = POST 触发后端任务 -> track() 轮询 /api/status/{task} -> 完成后刷新指定数据切片。
// 后端多 TTS 引擎/多音色类型由 config 透传，本层不感知引擎细节。
import { api } from './client.js'
import { store, toast, loadChunks, loadVoices, loadJobs, loadExports, loadContinuity, loadSystem, loadQc, loadProjects, loadEngines, loadDelivery, loadListen, hydrate } from '../data/store.js'
import { applyProgress } from '../data/progress.js'

const POLL_MS = 3000
const MAX_MIN = 60
const LOCK_MIN_MS = 350   // 蒙版最短驻留：POST 秒回时也闪一下，让用户确认「点到了」而非以为卡死
const START_GRACE_MS = 8000   // 确认启动宽限：后端 background task 在 POST 响应之后才置 running
const START_POLL_MS = 600      // 宽限期内快轮，确认越早蒙版撤得越早

let lockTimer = null
let lockSince = 0

// 全局启动蒙版：写动作 POST 在途时锁整页，杜绝连点重复提交。
// 长任务不长期锁——POST 确认启动后立即解锁，交给顶部 HUD 非阻断地显示进度。
function lockOn(text) {
  clearTimeout(lockTimer)
  lockSince = Date.now()
  store.lock.text = text
  store.lock.on = true
}

function lockOff() {
  const wait = Math.max(0, LOCK_MIN_MS - (Date.now() - lockSince))
  clearTimeout(lockTimer)
  lockTimer = setTimeout(() => { store.lock.on = false; store.lock.text = '' }, wait)
}

function guard() {
  if (store.mode !== 'live') {
    toast('演示模式：后端未连接，写操作不可用', 'warn')
    return false
  }
  return true
}

function upsertJob(task, name, type) {
  let j = store.jobs.find(x => x.task === task)
  if (!j) {
    j = { id: Date.now(), task, name, type, progress: 0, eta: '', status: 'running', logs: [], done: 0, total: 0, failed: 0, startedAt: Date.now() }
    store.jobs = [j, ...store.jobs]
  } else if (j.status !== 'running') {
    j.startedAt = Date.now(); j.done = 0; j.total = 0; j.failed = 0; j.progress = 0
  }
  j.status = 'running'
  j.name = name
  j.type = type
  return j
}

// 轮询单个任务直到结束：立即先读一次（启动即出进度），之后每 POLL_MS 一轮；超时 60 分钟。
// confirmStart=true（kick 起的任务）：后端是先 return 响应、background task 后置 running=True，
// 首读极可能读到 False。确认到 running 之前蒙版不撤、不做结束判定——否则 busy 秒清、
// 按钮回到可点的「重新生成」，连点照样重复提交。宽限 START_GRACE_MS 后仍未见 running，
// 视为秒完成任务（或后端没起来），交还主循环按结束处理。
async function pollTask(task, name, job, refreshers, confirmStart = false) {
  const deadline = Date.now() + MAX_MIN * 60000
  let logsLen = -1
  try {
    if (confirmStart) {
      const giveUpAt = Date.now() + START_GRACE_MS
      for (;;) {
        let s = null
        try { s = await api.status(task) } catch { /* 网络抖动下一轮重试 */ }
        if (s && s.running) break
        if (Date.now() >= giveUpAt) break
        await new Promise(r => setTimeout(r, START_POLL_MS))
      }
      lockOff()
    }
    for (;;) {
      let s = null
      try { s = await api.status(task) } catch { /* 单次网络失败下一轮重试 */ }
      if (s) {
        const logs = s.logs || []
        if (logs.length !== logsLen) {
          logsLen = logs.length
          job.logs = logs.slice(-8)
        }
        applyProgress(job, logs, !s.running)
        if (!s.running) { job.progress = 100; break }
      }
      if (Date.now() >= deadline) break
      await new Promise(r => setTimeout(r, POLL_MS))
    }
    job.status = 'done'
    for (const fn of refreshers) {
      try { await fn() } catch { /* 单切片刷新失败不影响其他 */ }
    }
    toast(`${name} 完成`, 'ok')
  } catch (e) {
    job.status = 'failed'
    toast(`${name} 失败：${e.message}`, 'err')
  } finally {
    store.busy[task] = false
  }
}

// 供 resyncRunning 用：后端已确认在跑，直接置忙并开轮询
async function track(task, name, type, refreshers) {
  store.busy[task] = true
  const job = upsertJob(task, name, type)
  if (!job.startedAt) job.startedAt = Date.now()   // 刷新接管的在跑任务补计时起点
  await pollTask(task, name, job, refreshers)
}

async function kick(promise, task, name, type, refreshers) {
  if (!guard()) return
  if (store.busy[task]) { toast(`${name} 正在进行中`, 'warn'); return }
  // 同步占位再发请求：杜绝「请求在途、busy 还没置真」窗口里的连点重复 POST
  store.busy[task] = true
  const job = upsertJob(task, name, type)
  lockOn(`正在启动「${name}」…`)
  try {
    await promise()
  } catch (e) {
    lockOff()
    store.busy[task] = false
    job.status = 'failed'
    toast(`${name} 启动失败：${e.message}`, 'err')
    return
  }
  // 蒙版保持到 pollTask 确认后端真的 running 才撤（见其 confirmStart 注释）
  await pollTask(task, name, job, refreshers, true)
}

// busy 是纯前端内存态：刷新页面后，后端真在跑的任务会显示成「没在跑」——
// 批量生成按钮又能点、也停不掉正在跑的任务。启动时向后端核对一遍真实状态，在跑就恢复跟踪。
export async function resyncRunning() {
  if (store.mode !== 'live') return
  const specs = [
    ['audio', '批量生成', 'tts', [loadChunks]],
    ['persona', '音色设计', 'persona', [loadVoices]],
    ['script', '剧本标注', 'annotate', [loadChunks, loadVoices]],
    ['review', '剧本复查', 'qc', [loadChunks]]
  ]
  // 并行查一遍，刷新后 1 个来回就恢复 busy/进度（串行会拖 4 个 RTT，按钮迟迟不亮）
  const states = await Promise.all(specs.map(([task]) => api.status(task).catch(() => null)))
  specs.forEach(([task, name, type, fns], i) => {
    const s = states[i]
    if (!s || !s.running || store.busy[task]) return
    toast(`检测到后端「${name}」任务进行中，已恢复进度跟踪`, 'warn')
    track(task, name, type, fns)
  })
}

export const actions = {
  // ---- 导入/剧本 ----
  uploadBook: (file) => {
    if (!guard()) return Promise.resolve(false)
    lockOn(`正在上传 ${file.name}…`)
    return api.upload(file)
      .then(() => { toast(`已上传 ${file.name}`, 'ok'); return true })
      .catch(e => { toast(`上传失败：${e.message}`, 'err'); return false })
      .finally(() => { lockOff(); loadSystem() })
  },
  generateScript: (opts) => kick(() => api.generateScript(opts || {}),
    'script', '剧本标注', 'annotate', [loadChunks, loadVoices, loadContinuity]),
  reviewScript: () => kick(() => api.reviewScript(),
    'review', '剧本复查', 'qc', [loadChunks, loadContinuity]),
  reviewContextual: (w) => kick(() => api.reviewContextual(w),
    'review', '上下文复查', 'qc', [loadChunks, loadContinuity]),

  // ---- 声音 ----
  generatePersonas: (opts) => kick(() => api.generatePersonas(opts || {}),
    'persona', '音色设计', 'persona', [loadVoices]),
  saveVoiceConfig: (configMap) => {
    if (!guard()) return Promise.resolve(false)
    lockOn('正在保存音色配置…')
    return api.saveVoiceConfig(configMap)
      .then(() => { toast('音色配置已保存', 'ok'); loadVoices(); return true })
      .catch(e => { toast(`保存失败：${e.message}`, 'err'); return false })
      .finally(lockOff)
  },

  // ---- 生成 ----
  editChunk: (index, patch) => {
    if (!guard()) return Promise.resolve(false)
    lockOn('正在保存修改…')
    return api.editChunk(index, patch)
      .then((c) => {
        const seg = store.segments[index]
        if (seg && c) {
          if (patch.text !== undefined) seg.text = c.text
          if (patch.instruct !== undefined) seg.instruct = c.instruct
          if (patch.speaker !== undefined) seg.speaker = String(patch.speaker).trim().toLowerCase().replace(/[\s_-]+/g, '')
        }
        return true
      })
      .catch(e => { toast(`编辑失败：${e.message}`, 'err'); return false })
      .finally(lockOff)
  },
  generateChunk: (index) => kick(() => api.generateChunk(index),
    'audio', '本段生成', 'tts', [loadChunks]),
  generatePending: () => {
    const indices = store.segments.filter(s => s.status !== 'done').map(s => s.id - 1)
    if (!indices.length) { toast('没有待生成段', 'warn'); return }
    kick(() => api.generateBatch(indices), 'audio', `批量生成 ${indices.length} 段`, 'tts', [loadChunks])
  },
  // 换声后必须重跑该角色的段，旧音频不会自己变；单角色重跑比重生成全书省几十倍
  generateSpeaker: (key) => {
    const indices = store.segments.filter(s => s.speaker === key).map(s => s.id - 1)
    if (!indices.length) { toast('该角色还没有台词段', 'warn'); return }
    kick(() => api.generateBatch(indices), 'audio', `重生成「${key}」${indices.length} 段`, 'tts', [loadChunks])
  },
  retryFailed: () => {
    const indices = store.segments.filter(s => s.status === 'error').map(s => s.id - 1)
    if (!indices.length) { toast('没有失败段', 'warn'); return }
    kick(() => api.generateBatch(indices), 'audio', `重试 ${indices.length} 个失败段`, 'tts', [loadChunks])
  },
  cancelAudio: () => {
    if (!guard()) return
    api.cancelAudio().then(() => toast('已请求中止生成', 'warn'))
      .catch(e => toast(`中止失败：${e.message}`, 'err'))
  },

  // ---- 审听（M3）：判定落 jsonl，计数一律回后端读，前端不自己攒一份平行账 ----
  listenVerdict: async (index, result, secs) => {
    if (!guard()) return false
    try {
      await api.prooflistenPut(index, result, Math.round(secs * 10) / 10)
      await loadListen()
      return true
    } catch (e) {
      toast(`审听记录失败：${e.message}`, 'err')
      return false
    }
  },

  // ---- 成品 ----
  mergeMp3: () => kick(() => api.merge(), 'audio', '合并 MP3', 'export', [loadChunks, loadDelivery, loadExports, loadSystem]),
  mergeM4b: (meta) => kick(() => api.mergeM4b({
    per_chunk_chapters: meta.perChunkChapters ?? true,
    title: meta.title || '', author: meta.author || '', narrator: meta.narrator || '',
    year: meta.year || '', description: meta.description || ''
  }), 'm4b_export', '导出 M4B', 'export', [loadDelivery, loadExports]),

  // ---- 多书切换：后端换软链并重启自身，前端只能轮询健康再整店刷新 ----
  async waitForEngine() {
    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      try { await api.stats(); return true } catch { await new Promise((r) => setTimeout(r, 3000)) }
    }
    return false
  },
  addProject: async (title) => {
    if (!guard()) return false
    if (store.busy.switch) { toast('切换已在进行中', 'warn'); return false }
    store.busy.switch = true
    lockOn('正在创建新书并切换…')
    let slug
    try {
      slug = (await api.addProject(title)).slug
      toast(`已创建《${title}》，切换中…`, 'warn')
    } catch (e) {
      lockOff()
      store.busy.switch = false
      toast(`新建失败：${e.message}`, 'err')
      return false
    }
    await new Promise((r) => setTimeout(r, 6000))
    const up = await actions.waitForEngine()
    lockOff()
    store.busy.switch = false
    if (!up) { toast('服务 3 分钟未恢复：显存不足？查 logs/switch.log', 'err'); return false }
    await hydrate()
    toast(`已切到新书《${store.project.title}》，去「导入拆解」上传正文`, 'ok')
    return true
  },
  switchProject: async (slug) => {
    if (!guard()) return false
    if (store.busy.switch) { toast('切换已在进行中', 'warn'); return false }
    store.busy.switch = true
    lockOn('正在切换工作区（服务重启中）…')
    try {
      await api.switchProject(slug)
      toast(`切换《${slug}》：服务重启中…`, 'warn')
    } catch (e) {
      lockOff()
      store.busy.switch = false
      toast(`切换启动失败：${e.message}`, 'err')
      return false
    }
    await new Promise((r) => setTimeout(r, 6000))
    const up = await actions.waitForEngine()
    lockOff()
    store.busy.switch = false
    if (!up) {
      toast('服务 3 分钟未恢复：显存不足？查 logs/switch.log', 'err')
      return false
    }
    await hydrate()
    toast(`已切换到《${store.project.title}》`, 'ok')
    return true
  },

  refreshAll: () => { loadProjects(); loadEngines(); loadChunks(); loadVoices(); loadJobs(); loadDelivery(); loadListen(); loadExports(); loadSystem(); loadQc() }
}
