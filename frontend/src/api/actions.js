// 写路径动作层：组件只调动作，不碰 fetch/轮询。
// 每个动作 = POST 触发后端任务 -> track() 轮询 /api/status/{task} -> 完成后刷新指定数据切片。
// 后端多 TTS 引擎/多音色类型由 config 透传，本层不感知引擎细节。
import { api } from './client.js'
import { store, toast, loadChunks, loadVoices, loadJobs, loadExports, loadContinuity, loadSystem, loadQc, loadProjects, loadEngines, loadDelivery, loadListen, hydrate } from '../data/store.js'

const POLL_MS = 3000
const MAX_MIN = 60

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
    j = { id: Date.now(), task, name, type, progress: 0, eta: '', status: 'running', logs: [] }
    store.jobs = [j, ...store.jobs]
  }
  j.status = 'running'
  j.name = name
  j.type = type
  return j
}

async function track(task, name, type, refreshers) {
  store.busy[task] = true
  const job = upsertJob(task, name, type)
  const deadline = Date.now() + MAX_MIN * 60000
  let logsLen = 0
  try {
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, POLL_MS))
      let s
      try { s = await api.status(task) } catch { continue }
      const logs = s.logs || []
      if (logs.length !== logsLen) {
        logsLen = logs.length
        job.logs = logs.slice(-8)
        job.progress = Math.min(95, Math.round((logs.length / Math.max(1, logsLen)) * 100) || 50)
      }
      if (!s.running) { job.progress = 100; break }
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
    loadJobs()
  }
}

async function kick(promise, task, name, type, refreshers) {
  if (!guard()) return
  if (store.busy[task]) { toast(`${name} 正在进行中`, 'warn'); return }
  try {
    await promise()
  } catch (e) {
    toast(`${name} 启动失败：${e.message}`, 'err')
    return
  }
  track(task, name, type, refreshers)
}

export const actions = {
  // ---- 导入/剧本 ----
  uploadBook: (file) => {
    if (!guard()) return Promise.resolve(false)
    return api.upload(file)
      .then(() => { toast(`已上传 ${file.name}`, 'ok'); return true })
      .catch(e => { toast(`上传失败：${e.message}`, 'err'); return false })
      .finally(() => { loadSystem() })
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
    return api.saveVoiceConfig(configMap)
      .then(() => { toast('音色配置已保存', 'ok'); loadVoices(); return true })
      .catch(e => { toast(`保存失败：${e.message}`, 'err'); return false })
  },

  // ---- 生成 ----
  editChunk: (index, patch) => {
    if (!guard()) return Promise.resolve(false)
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
    let slug
    try {
      slug = (await api.addProject(title)).slug
      toast(`已创建《${title}》，切换中…`, 'warn')
    } catch (e) {
      store.busy.switch = false
      toast(`新建失败：${e.message}`, 'err')
      return false
    }
    await new Promise((r) => setTimeout(r, 6000))
    const up = await actions.waitForEngine()
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
    try {
      await api.switchProject(slug)
      toast(`切换《${slug}》：服务重启中…`, 'warn')
    } catch (e) {
      store.busy.switch = false
      toast(`切换启动失败：${e.message}`, 'err')
      return false
    }
    await new Promise((r) => setTimeout(r, 6000))
    const up = await actions.waitForEngine()
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
