// 数据层：reactive 单一 store + 细粒度 loader（读路径）。
// 写路径在 actions.js：动作 -> 后端任务 -> pollTask -> 重新 load 对应切片。
// mock 回退保证无后端时（如 Qoder Site 演示）页面照常工作。
import { reactive } from 'vue'
import { store as mockStore, fmtTime } from './mock.js'
import { api } from '../api/client.js'

const KNOWN_NAMES = { narrator: '旁白', chenmo: '陈默', linwan: '林晚', oldzhou: '老周', xiaoman: '小满' }
const PALETTE = ['#7c6cff', '#e06fa8', '#f5b93f', '#34d6c6', '#ff8f6b', '#8fd14f', '#6fb3ff', '#d1f06f']
const KEY_ALIASES = { laoqiang: 'oldzhou', laozhou: 'oldzhou', zhoubo: 'oldzhou' }

export function speakerKey(label) {
  const raw = String(label || 'narrator').trim().toLowerCase().replace(/[\s_-]+/g, '')
  return KEY_ALIASES[raw] || raw
}

// 这些键必须在 reactive() 之前放进对象。事后赋值的新键不被 Vue 追踪，
// 读它们的 computed 会永远缓存初值——TransportBar 的 live 就是这么卡成 false、
// 播放按钮点了没反应的。
export const store = reactive(Object.assign(structuredClone(mockStore), {
  mode: 'mock',
  busy: {},          // task -> true，按钮防重
  toast: [],         // { text, kind }
  projects: { active: null, list: [] },   // 多书注册表快照
  engines: []        // 服务端 engines.ENGINES：出声引擎下拉框唯一来源
}))

// 四类分开记：机检（ASR 只对文本）测不到「音色不对」和念成另一个合法读音的错读，
// 一个平均数会把问题藏起来。见 docs/post-production-plan.md §M3。
export const VERDICT = { ok: '对', misread: '错读', timbre: '音色不对', regen: '需重生成' }
export const VERDICT_ICON = { ok: '✓', misread: '✗', timbre: '♪', regen: '↻' }
export const VERDICT_ORDER = Object.keys(VERDICT)
export const VERDICT_HELP = {
  ok: '念对了、音色对（1）',
  misread: '字念错 / 多音字念成另一个合法读音 / 数字串读反（2）——机检测不出这一类',
  timbre: '字对但音色漂移、语气不对（3）——design 逐句重抽的典型症状，机检全盲',
  regen: '本段要重生成（4）：算返工率的分子'
}

export function speakerOf(id) {
  return store.speakers[id] || { name: id, color: '#666' }
}
export { fmtTime }

// chunk.voice_engine（qwen/cosy/index/kokoro）→ 展示名；未下发时按引擎 key 原样显示
export function engineLabel(key) {
  if (!key || key === 'qwen') return 'Qwen3-TTS'
  const row = store.engines.find((e) => e.key === key)
  return row ? row.label : key
}

export function toast(text, kind = 'info') {
  store.toast.push({ text, kind, at: Date.now() })
  setTimeout(() => { store.toast = store.toast.filter((t) => t.text !== text || Date.now() - t.at < 1200) }, 4200)
}

function ensureSpeaker(key) {
  if (!store.speakers[key]) {
    if (key === 'narrator') {
      store.speakers[key] = { name: '旁白', color: '#8fa3bf' }
    } else {
      const idx = Object.keys(store.speakers).filter(k => k !== 'narrator').length
      store.speakers[key] = { name: KNOWN_NAMES[key] || key, color: PALETTE[idx % PALETTE.length] }
    }
  }
  return store.speakers[key]
}

const MODE_BY_TYPE = { clone: 'clone', custom: 'custom', design: 'design', lora: 'lora' }

// ---------- 各数据切片 loader（hydrate 与写路径动作共用） ----------

export async function loadSystem() {
  const [stats, config] = await Promise.all([api.stats(), api.config()])
  store.system = {
    gpuUsed: stats.gpu?.allocated_gb ?? 0,
    gpuTotal: Math.round(stats.gpu?.total_gb ?? 0),
    freeGb: Math.round(stats.disk?.free_gb ?? 0),
    ollama: config.llm?.model_name || '—',
    ready: true,
    continuity: store.system.continuity || null,
    qc: store.system.qc || null,
    delivery: store.system.delivery || null,
    listen: store.system.listen || null,
    ttsMode: config.tts?.mode || 'local'
  }
}

// 出声引擎清单：voice_config 的 engine 下拉框与 chunk 溯源徽标共用这一份，前端不写死
export async function loadEngines() {
  try { store.engines = await api.engines() } catch { /* 老后端无此端点，下拉框退化为仅 Qwen */ }
}

export async function loadChunks() {
  const chunks = await api.chunks()
  if (!Array.isArray(chunks) || !chunks.length) return false
  const lineCounts = {}
  store.segments = chunks.map((c, i) => {
    const key = speakerKey(c.speaker)
    ensureSpeaker(key)
    lineCounts[key] = (lineCounts[key] || 0) + 1
    return {
      id: i + 1,
      order: i + 1,
      speaker: key,
      kind: key === 'narrator' ? 'narration' : 'dialogue',
      text: c.text,
      instruct: c.instruct || '',
      duration: 0,
      status: c.status === 'done' ? 'done' : c.status === 'error' ? 'error' : c.status === 'generating' ? 'generating' : 'pending',
      audioPath: c.audio_path ? (c.audio_path.startsWith('/') ? c.audio_path : '/' + c.audio_path.replace(/^\.?\//, '')) : null,
      // 实际出声引擎与兜底标记：Kokoro 顶班时必须可见，不能冒充角色音色
      engine: c.voice_engine || '',
      fallback: !!c.voice_fallback,
      qc: null,
      qcErr: null,
      listen: null,    // 审听判定：必须在此声明，事后挂到段上不被追踪，高亮不会跟着变
      versions: 1,
      chosen: i + 1
    }
  })
  store._lineCounts = lineCounts
  store.chapters = [{
    id: 1, title: '当前书籍', duration: 0,
    status: store.segments.every(s => s.status === 'done') ? 'generated' : 'annotated'
  }]
  return true
}

export async function loadVoices() {
  const voices = await api.voices()
  if (!Array.isArray(voices) || !voices.length) return false
  const counts = store._lineCounts || {}
  const characters = []
  const voiceRows = []
  for (const v of voices) {
    const key = speakerKey(v.name)
    ensureSpeaker(key)
    const type = v.config?.type || 'design'
    const eng = v.config?.engine || ''
    // 只有真正带音色配置（design 跑过 / clone 绑过参考音频）才算已绑定
    const voiceId = (!v.persona_pending && v.config?.type) ? `v-${key}-1` : null
    if (voiceId) {
      voiceRows.push({
        id: voiceId,
        name: `${speakerOf(key).name}·${type}`,
        mode: MODE_BY_TYPE[type] || 'design',
        engine: eng,
        model: eng && eng !== 'qwen' ? engineLabel(eng) : type === 'clone' ? 'Base' : type === 'custom' ? 'CustomVoice' : 'VoiceDesign',
        locked: true,
        dur: '—',
        label: v.name,
        config: v.config || null,
        refAudio: v.config?.ref_audio ? '/' + String(v.config.ref_audio).replace(/^\.?\//, '') : null
      })
    }
    characters.push({
      id: key,
      label: v.name,
      name: speakerOf(key).name,
      aliases: [],
      lines: counts[key] || 0,
      desc: voiceId ? (v.config?.description || '已绑定音色') : '音色待设计',
      engine: eng,
      config: v.config || null,
      voiceId
    })
  }
  store.characters = characters
  store.voices = voiceRows
  return true
}

const JOB_NAMES = {
  script: ['剧本标注', 'annotate'],
  review: ['剧本复查', 'qc'],
  persona: ['音色设计', 'persona'],
  audio: ['TTS 生成/合并', 'tts'],
  m4b_export: ['M4B 导出', 'export']
}

export async function loadJobs() {
  const jobs = []
  let id = 1
  for (const [task, [name, type]] of Object.entries(JOB_NAMES)) {
    try {
      const s = await api.status(task)
      const logs = s.logs || []
      jobs.push({
        id: id++, task, name, type,
        progress: s.running ? 50 : 100,
        eta: s.running ? '—' : '',
        status: s.running ? 'running' : 'done',
        logs: logs.slice(-8)
      })
    } catch { /* 任务不可达则跳过 */ }
  }
  store.jobs = jobs
}

export async function loadContinuity() {
  try {
    const rep = await api.continuity()
    if (rep && Array.isArray(rep.chunks)) {
      store.system.continuity = { sim: rep.similarity, missing: rep.missing_chars, added: rep.added_chars }
      for (const c of rep.chunks) {
        const seg = store.segments[c.index]
        if (seg) seg.qc = c.status === 'ok' ? 'pass' : 'retry'
      }
    }
  } catch { /* 大书校验超时，不阻塞 */ }
}

// SQLite 侧权威质检（规则引擎 + ASR 音频回听）。覆盖 continuity 的文本一致结论，
// 因为"音频实际念了什么"比"剧本文本对不对"更贴近成品。
export async function loadQc() {
  try {
    const rep = await api.qc()
    if (!rep || !Array.isArray(rep.segments)) return
    store.system.qc = rep.totals || null
    for (const q of rep.segments) {
      const seg = store.segments[q.ord]
      if (!seg) continue
      seg.qcErr = q.err ?? null
      if (q.qc) seg.qc = q.qc
    }
  } catch { /* 无 QC 库，不阻塞 */ }
}

// 多书工作区：注册表列出全部项目，active 即当前软链指向的书。
export async function loadProjects() {
  try {
    const rep = await api.projects()
    const list = rep.projects || []
    store.projects = { active: rep.active, list }
    const cur = list.find((p) => p.active)
    if (cur) store.project.title = cur.title
  } catch { /* 后端无多书注册表时维持单书显示 */ }
}

// 成品列表：探测服务器上实际存在的整书产物（MP3 合并 / M4B 导出），有就列出可播可下载。
export async function loadExports() {
  const rows = []
  const probes = [
    { url: '/api/audiobook', format: 'MP3', label: '合并成品' },
    { url: '/api/audiobook_m4b', format: 'M4B', label: '章节版' }
  ]
  const name = store.project.title || '当前书籍'
  for (const [i, p] of probes.entries()) {
    try {
      // 本环境 FastAPI 对 HEAD 返回 405，用 1 字节 Range GET 探测存在性与总大小
      const res = await fetch(p.url, { headers: { Range: 'bytes=0-0' }, signal: AbortSignal.timeout(4000) })
      if (!res.ok) continue
      const cr = res.headers.get('content-range') || ''
      let size = Number(cr.split('/')[1] || 0)
      if (res.status === 200) {
        size = Number(res.headers.get('content-length') || 0)
        res.body && res.body.cancel()
      }
      rows.push({
        id: i + 1, name: `${name} · ${p.label}`, format: p.format,
        size: size ? `${(size / 1048576).toFixed(1)} MB` : '—',
        chapters: store.chapters.length, time: '—', url: p.url
      })
    } catch { /* 服务未起或无该产物 */ }
  }
  // 机检不通过的成品还能试听，但不能当成可交付物下载；报告的 `通过` 是唯一判据。
  const blocked = !!(store.system.delivery && store.system.delivery.通过 === false)
  store.exports = rows.map((r) => ({ ...r, blocked }))
}

// 母带机检报告（M1 闸门）。老后端没这个端点 → null，UI 退化成「未机检」。
export async function loadDelivery() {
  try { store.system.delivery = await api.deliveryReport() } catch { store.system.delivery = null }
}

// 审听进度（M3）。`最新` 的 key 是 0 基段号，和 loadQc 用同一个下标。
export async function loadListen() {
  try {
    const rep = await api.prooflisten()
    store.system.listen = rep
    for (const [ord, res] of Object.entries(rep.最新 || {})) {
      const seg = store.segments[Number(ord)]
      if (seg) seg.listen = res
    }
  } catch { store.system.listen = null }
}

// ---------- 总入口 ----------

export async function hydrate() {
  try {
    await loadSystem()
    store.mode = 'live'
    await loadProjects()
    await loadEngines()
    await loadChunks()
    await loadVoices()
    await loadContinuity()
    await loadQc()
    await loadListen()
    await loadJobs()
    await loadDelivery()
    await loadExports()
  } catch {
    // 切换重启期间的失败不是“掉线”，别把 live 打回 mock（顶栏下拉会消失）
    if (!store.busy.switch) store.mode = 'mock'
  }
  return store.mode
}
