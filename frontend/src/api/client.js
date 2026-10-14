// 同源 API 客户端：联调版由后端 :4200 直接托管 dist；dev 模式由 vite 代理
// 约定：本层只做传输（GET/POST/上传/HEAD），不含业务映射；业务在 actions.js / store.js
const BASE = ''

async function request(path, options = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), options.timeoutMs || 8000)
  try {
    const res = await fetch(BASE + path, {
      method: options.method || 'GET',
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: ctrl.signal
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      throw new Error(`${res.status} ${detail || res.statusText}`)
    }
    if (options.noContent) return { ok: true }
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

// 空值不进 query：后端每个筛选项都有默认值，传空串等于不筛
function qs(params) {
  const p = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) p.set(k, String(v))
  })
  return p.toString()
}

export const api = {
  // ---- 读 ----
  stats: () => request('/api/system/stats', { timeoutMs: 4000 }),
  config: () => request('/api/config', { timeoutMs: 4000 }),
  chunks: () => request('/api/chunks'),
  annotatedScript: () => request('/api/annotated_script'),
  voices: () => request('/api/voices'),
  status: (task) => request(`/api/status/${task}`, { timeoutMs: 5000 }),
  continuity: () => request('/api/continuity', { timeoutMs: 25000 }),
  qc: () => request('/api/qc'),
  deliveryReport: () => request('/api/delivery_report'),
  prooflisten: () => request('/api/prooflisten'),
  prooflistenPut: (ord, result, secs) => request(`/api/prooflisten?${qs({ ord, result, secs })}`, { method: 'POST', timeoutMs: 8000 }),
  projects: () => request('/api/projects', { timeoutMs: 5000 }),
  scriptMap: () => request('/api/script_map', { timeoutMs: 8000 }),

  // ---- 写 ----
  upload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(BASE + '/api/upload', { method: 'POST', body: fd })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json() })
  },
  cloneVoiceUpload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(BASE + '/api/clone_voices/upload', { method: 'POST', body: fd })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json() })
  },
  generateScript: (opts) => request('/api/generate_script', { method: 'POST', body: opts || {}, timeoutMs: 15000 }),
  reviewScript: () => request('/api/review_script', { method: 'POST', timeoutMs: 15000 }),
  reviewContextual: (windowSize) => request('/api/review_script_contextual', { method: 'POST', body: { window_size: windowSize || 4 }, timeoutMs: 15000 }),
  generatePersonas: (opts) => request('/api/generate_personas', { method: 'POST', body: opts || {}, timeoutMs: 15000 }),
  saveVoiceConfig: (configMap) => request('/api/save_voice_config', { method: 'POST', body: configMap, timeoutMs: 15000 }),
  editChunk: (index, patch) => request(`/api/chunks/${index}`, { method: 'POST', body: patch, timeoutMs: 15000 }),
  generateChunk: (index) => request(`/api/chunks/${index}/generate`, { method: 'POST', timeoutMs: 15000 }),
  generateBatch: (indices) => request('/api/generate_batch', { method: 'POST', body: { indices }, timeoutMs: 15000 }),
  cancelAudio: () => request('/api/cancel_audio', { method: 'POST', timeoutMs: 15000 }),
  // ---- Voice Lab（声音实验室）----
  cloneVoices: () => request('/api/clone_voices/list', { timeoutMs: 5000 }),
  // 回写参考音频的 ASR 转写，落 clone_voices/manifest.json，选样时回填用
  cloneVoiceRefText: (body) => request('/api/clone_voices/ref_text', { method: 'POST', body, timeoutMs: 8000 }),
  engines: () => request('/api/engines', { timeoutMs: 5000 }),
  emotions: () => request('/api/emotions', { timeoutMs: 5000 }),
  voiceLabModels: () => request('/api/voice_lab/models', { timeoutMs: 8000 }),
  voiceTemplates: () => request('/api/voice_templates', { timeoutMs: 6000 }),
  voiceLabHistory: (params) => request(`/api/voice_lab/history?${qs(params)}`, { timeoutMs: 8000 }),
  voiceLabRecordUpdate: (body) => request('/api/voice_lab/record/update', { method: 'POST', body, timeoutMs: 15000 }),
  voiceTemplateSave: (body) => request('/api/voice_templates', { method: 'POST', body, timeoutMs: 8000 }),
  voiceLabRecordDelete: (body) => request('/api/voice_lab/record/delete', { method: 'POST', body, timeoutMs: 15000 }),
  // 同步生成：含模型冷加载最坏 ~3 分钟
  voiceLabGenerate: (body) => request('/api/voice_lab/generate', { method: 'POST', body, timeoutMs: 300000 }),
  // ASR 自动转写参考音频 -> ref_text（SenseVoice sidecar，见 ttslab/asr_server.py）
  transcribeRef: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(BASE + '/api/voice_lab/transcribe_ref', { method: 'POST', body: fd })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json() })
  },

  // ---- 音频仓库（标签词表来自 /api/vault/schema，前端不写死维度）----
  vaultSchema: () => request('/api/vault/schema', { timeoutMs: 5000 }),
  vaultList: (params) => request(`/api/vault/list?${qs(params)}`, { timeoutMs: 15000 }),
  vaultPick: (params) => request(`/api/vault/pick?${qs(params)}`, { timeoutMs: 15000 }),
  vaultAdd: (body) => request('/api/vault/add', { method: 'POST', body, timeoutMs: 60000 }),
  vaultUpdate: (body) => request('/api/vault/update', { method: 'POST', body, timeoutMs: 15000 }),
  vaultDelete: (id, purge) => request(`/api/vault/${id}?purge=${purge ? 'true' : 'false'}`, { method: 'DELETE', timeoutMs: 15000 }),

  merge: () => request('/api/merge', { method: 'POST', timeoutMs: 15000 }),
  mergeM4b: (meta) => request('/api/merge_m4b', { method: 'POST', body: meta, timeoutMs: 15000 }),
  // 切换会重启后端：请求本身很快返回，恢复与否由调用方轮询 stats
  switchProject: (slug) => request(`/api/projects/switch?slug=${encodeURIComponent(slug)}`, { method: 'POST', timeoutMs: 15000 }),
  addProject: (title) => request(`/api/projects/add?title=${encodeURIComponent(title)}`, { method: 'POST', timeoutMs: 15000 })
}
