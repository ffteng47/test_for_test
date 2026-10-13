<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">声音实验室 · Voice Lab</div>
        <div class="view-sub">选方法 → 选模型（可多选对比）→ 统一试听文本 → 生成；每条结果标注来源模型，纵向排列 A/B</div>
      </div>
      <div class="head-actions">
        <span class="chip chip-dim">{{ store.mode === 'live' ? 'LIVE' : '演示模式不可生成' }}</span>
      </div>
    </div>

    <div class="layout">
      <!-- 左侧：参数 -->
      <div class="col card">
        <div class="col-head">
          <span class="label">01 · 造声参数</span>
        </div>

        <div class="field">
          <div class="label">目标角色（选用时写入其音色配置）</div>
          <select v-model="speakerLabel">
            <option v-for="c in store.characters" :key="c.id" :value="c.label">
              {{ c.name }}（{{ c.label }} · {{ c.lines }} 段）
            </option>
          </select>
        </div>

        <div class="field">
          <div class="label">生成方法</div>
          <div class="tabs">
            <button v-for="m in methods" :key="m.key" class="tab" :class="{ on: method === m.key }"
                    @click="switchMethod(m.key)">{{ m.name }}<span class="tab-n">{{ countByMethod[m.key] || 0 }}</span></button>
          </div>
          <div class="hint">{{ METHOD_HINT[method] }} · 其余引擎在别的页签下（IndexTTS-2 / CosyVoice2 走「参考克隆」，Kokoro 走「内置音色」）</div>
        </div>

        <div class="field" v-if="method === 'design'">
          <div class="label">音色描述（自然语言，越具体越好）</div>
          <select class="tpl" v-model="voiceTpl" @change="applyVoiceTpl">
            <option value="">📋 从模板填充…（预置 {{ VOICE_TEMPLATES.length }} · 模板库 {{ libVoices.length }}）</option>
            <option v-for="(t, i) in allVoiceTpls" :key="i" :value="i">{{ t.name }}</option>
          </select>
          <textarea v-model="description" rows="4" placeholder="如：少年男声，明亮俏皮，带一点顽劣的尾音，语速中等"></textarea>
          <button class="btn btn-ghost btn-sm" @click="saveAsTpl('voice', description)">＋ 当前描述存为音色模板</button>
        </div>

        <template v-if="method === 'clone'">
          <div class="field">
            <div class="label">参考音频（先「导入参考声音」上传）</div>
            <select v-model="refAudio">
              <option value="">— 选择已上传样本 —</option>
              <option v-for="v in cloneList" :key="v.filename" :value="v.filename">{{ v.name }}</option>
            </select>
            <button class="btn btn-ghost btn-sm" :disabled="uploading" @click="$refs.labFile.click()">
              {{ uploading ? '上传中…' : '＋ 上传新样本' }}
            </button>
            <input ref="labFile" type="file" accept=".wav,.mp3,.flac,.ogg" style="display:none" @change="onRefFile" />
            <div class="ref-play" v-if="refAudio">
              <audio :src="`/clone_voices/${refAudio}`" controls preload="none"></audio>
              <div class="hint">试听参考音频。克隆音色完全由这段录音决定：要老人声就得有老人录音，风格指令改不了年龄。</div>
            </div>
          </div>
          <div class="field">
            <div class="label">参考音频对应台词（ref_text，必填）</div>
            <textarea v-model="refText" rows="2"></textarea>
          </div>
          <div class="field">
            <div class="label">情绪指令 · 仅「CosyVoice2 情感指令」模型生效（改语气，不改年龄音色）</div>
            <select class="tpl" value="" @change="fillStyle('description', $event.target.value)">
              <option value="">📋 从规范情感词表填充…（{{ styleOptions.length }} 项）</option>
              <option v-for="o in styleOptions" :key="o.emotion" :value="o.instruct">{{ o.instruct }}</option>
              <optgroup v-if="libEmotions.length" label="📚 模板库情绪指令">
                <option v-for="o in libEmotions" :key="o.id" :value="o.text">{{ o.name }}</option>
              </optgroup>
            </select>
            <input v-model="description" placeholder="如：用愤怒压抑的语气，语速偏慢" />
            <button class="btn btn-ghost btn-sm" @click="saveAsTpl('emotion', description)">＋ 当前指令存为模板</button>
            <div class="hint">「CosyVoice2 克隆」是纯 zero-shot，音色完全来自上面的参考音频；想要老人声就录一段老人参考音频，写指令是没用的。</div>
          </div>
        </template>

        <template v-if="method === 'custom'">
          <div class="field">
            <div class="label">内置说话人</div>
            <input v-model="voice" placeholder="Ryan / Serena / Uncle_Fei …" />
          </div>
          <div class="field">
            <div class="label">风格指令（instruct）</div>
            <select class="tpl" value="" @change="fillStyle('instruct', $event.target.value)">
              <option value="">📋 从规范情感词表填充…（{{ styleOptions.length }} 项）</option>
              <option v-for="o in styleOptions" :key="o.emotion" :value="o.instruct">{{ o.instruct }}</option>
              <optgroup v-if="libEmotions.length" label="📚 模板库情绪指令">
                <option v-for="o in libEmotions" :key="o.id" :value="o.text">{{ o.name }}</option>
              </optgroup>
            </select>
            <input v-model="instruct" placeholder="如：calm, gentle, elderly male" />
            <button class="btn btn-ghost btn-sm" @click="saveAsTpl('emotion', instruct)">＋ 当前指令存为模板</button>
          </div>
        </template>

        <div class="field">
          <div class="label">试听文本（同一文本才能横向可比）</div>
          <textarea v-model="sampleText" rows="3"></textarea>
          <div class="hint" v-if="firstLineOfSpeaker">已默认填入该角色第一句台词，可改</div>
        </div>

        <div class="field">
          <div class="label">seed（-1 随机；固定后可跨模型对比）</div>
          <input type="number" v-model.number="seed" style="width:110px" />
        </div>

        <div class="field">
          <div class="label">模型（多选 = 纵向并排对比，逐个生成）</div>
          <div class="model-box">
            <label v-for="mo in modelsForMethod" :key="mo.key" class="model-item">
              <input type="checkbox" :value="mo.key" v-model="picked" :disabled="!mo.available" />
              <span class="model-name">{{ mo.label }}</span>
              <span class="chip" :class="mo.available ? 'chip-ok' : 'chip-off'">
                {{ mo.loaded ? '已驻显存' : mo.available ? '可加载' : '未下载' }}
              </span>
            </label>
          </div>
        </div>

        <div class="field" style="padding-bottom:16px">
          <button class="btn btn-primary gen-btn" :disabled="busy || !picked.length || store.mode !== 'live'" @click="generate">
            {{ busy ? `生成中（${doneCount}/${picked.length}）…` : `▶ 生成试听（${picked.length} 个模型）` }}
          </button>
          <div class="hint">首次切模型需加载权重（约 1 分钟），之后每次几秒。</div>
        </div>
      </div>

      <!-- 右侧：结果纵向对比 -->
      <div class="col card">
        <div class="col-head">
          <span class="label">02 · 试听对比</span>
          <span class="chip chip-dim">{{ results.length }} 条</span>
        </div>
        <div v-if="genError" class="err-box">{{ genError }}</div>
        <div v-for="r in results" :key="r.id" class="result-row">
          <div class="r-meta">
            <div class="r-model">{{ r.name || r.model_label }}<button class="btn btn-ghost btn-sm" @click="renameRec(r)">✎</button><span class="r-time">· {{ r.gen_time_s }}s 生成 / {{ r.duration_s }}s 音频 · seed {{ r.seed }}</span></div>
            <div class="r-line dim mono">{{ r.sample_text }}</div>
            <div class="r-desc dim" v-if="r.description">{{ r.description }}</div>
          </div>
          <div class="r-acts">
            <audio :src="r.audio_url" controls preload="none"></audio>
            <button class="btn btn-sm" :class="{ 'btn-used': isUsed(r) }" :disabled="!!applying" @click="useOrUnlock(r)">
              {{ applying === r.id ? '绑定中…' : isUsed(r) ? `已选用 → ${boundCharOf(r).name}` : `选用 → ${currentCharName}` }}
            </button>
          </div>
        </div>
        <div class="dim lib-empty" v-if="!results.length && !busy">
          还没有试听结果。左侧配好参数点「生成试听」，多模型结果会自上而下排列，方便对照。
        </div>

        <div class="col-head hist-head">
          <span class="label">历史 · {{ histTotal }} 条（第 {{ histPage }}/{{ histPages }} 页）</span>
          <span class="hist-tools">
            <select v-model="histSpeaker" @change="loadHistory(0)">
              <option value="">全部角色</option>
              <option v-for="c in store.characters" :key="c.id" :value="c.label">{{ c.name }}</option>
            </select>
            <button class="btn btn-sm" :disabled="histOffset <= 0" @click="loadHistory(histOffset - histLimit)">← 上页</button>
            <button class="btn btn-sm" :disabled="histOffset + histLimit >= histTotal" @click="loadHistory(histOffset + histLimit)">下页 →</button>
            <label class="purge"><input type="checkbox" v-model="purgeFile" />删除时连音频</label>
          </span>
        </div>
        <div v-for="r in history" :key="'h'+r.id" class="result-row hist-row">
          <div class="r-meta">
            <div class="r-model">{{ r.name || r.model_label }}
              <button class="btn btn-ghost btn-sm" @click="renameRec(r)">✎</button>
              <span class="r-time">· {{ r.created_at }} · seed {{ r.seed }}<template v-if="r.speaker"> · 目标 {{ r.speaker }}</template></span>
            </div>
            <textarea class="r-text" rows="2" :value="r.sample_text" @change="patchText(r, $event.target.value)"></textarea>
            <div class="r-desc dim" v-if="r.description">{{ r.description }}</div>
            <div class="hist-tags" v-if="editing !== r.id">
              <span class="chip chip-dim" v-for="(v, k) in (r.tags || {})" :key="k">{{ k }}={{ Array.isArray(v) ? v.join('/') : v }}</span>
              <button class="btn btn-ghost btn-sm" @click="openTag(r)">标注</button>
            </div>
            <div class="hist-tags editing" v-else>
              <TagEditor :facets="facets" v-model="editTags" />
            </div>
          </div>
          <div class="r-acts">
            <audio :src="r.audio_url" controls preload="none"></audio>
            <button v-if="editing === r.id" class="btn btn-sm btn-primary" :disabled="saving === r.id" @click="saveTags(r)">
              {{ saving === r.id ? '保存中…' : '保存标注' }}
            </button>
            <button v-if="editing === r.id" class="btn btn-sm btn-ghost" @click="editing = ''">取消</button>
            <button class="btn btn-sm" :class="{ 'btn-used': isUsed(r) }" :disabled="applying === r.id" @click="useOrUnlock(r)">
              {{ applying === r.id ? '绑定中…' : isUsed(r) ? `已选用 → ${boundCharOf(r).name}` : `选用 → ${currentCharName}` }}
            </button>
            <button class="btn btn-sm" :disabled="saving === r.id" @click="toVault(r)">
              {{ saving === r.id ? '入库中…' : '存仓库' }}
            </button>
            <button class="btn btn-sm btn-ghost" :disabled="saving === r.id" @click="dropRecord(r)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <transition name="mask">
      <div v-if="applying" class="apply-mask">
        <div class="spin"></div>
        <div class="apply-txt">正在把这条声音绑定到「{{ currentCharName }}」…</div>
      </div>
    </transition>
  </div>
</template>

<script>
import { store, toast } from '../data/store.js'
import { actions } from '../api/actions.js'
import { api } from '../api/client.js'
import TagEditor from '../components/TagEditor.vue'

const METHOD_HINT = {
  design: '文字描述凭空造音色（VoiceDesign），产出的预览音即为该角色的克隆参考',
  clone: '用已上传的真实录音做克隆试听（Base），可加风格指令验证 instruct 效果',
  custom: '内置说话人 + 风格指令（CustomVoice），适合快速拿标准音色'
}

// 音色描述模板：维度对齐 ElevenLabs Voice Design（性别/年龄/口音/音高/质感/性格/语速）
// 与「风格指令」是两个轴——这里描述的是嗓子长什么样，那边描述这句怎么念（词表来自 /api/emotions）
const VOICE_TEMPLATES = [
  { name: '旁白 · 沉稳', text: '中年男性，中低音，音色干净浑厚，标准普通话，语速不紧不慢，克制而有画面感' },
  { name: '旁白 · 亲和', text: '青年女性，声音温暖柔和，带轻微气声，语速中等偏慢，像给孩子讲故事' },
  { name: '男童 · 顽皮', text: '10 岁男孩，明亮跳脱，音调偏高，吐字快而含糊，带狡黠的笑意' },
  { name: '少女 · 怯生', text: '十五六岁少女，声音细软偏轻，略带紧张颤音，语速慢，句尾上扬' },
  { name: '老者 · 沙哑', text: '七十岁老人，低沉沙哑，气息短促，语速缓慢，每句像叹气的收尾' },
  { name: '中年 · 威严', text: '四十多岁男性，胸腔共鸣重，咬字果断，语速偏快，不容置疑的语调' },
  { name: '反派 · 阴柔', text: '青年男性，音色偏冷，慢条斯理，尾音拖长带讥讽' }
]

export default {
  name: 'VoiceLabView',
  data() {
    return {
      store,
      METHOD_HINT,
      VOICE_TEMPLATES,
      voiceTpl: '',
      libVoices: [],
      libEmotions: [],
      methods: [
        { key: 'design', name: '描述造声' },
        { key: 'clone', name: '参考克隆' },
        { key: 'custom', name: '内置音色' }
      ],
      method: 'design',
      models: [],
      cloneList: [],
      styleOptions: [],
      applying: '',
      unlocked: [],
      picked: ['vd17'],
      speakerLabel: null,
      description: '',
      refAudio: '',
      refText: '',
      voice: 'Ryan',
      instruct: '',
      sampleText: '',
      seed: -1,
      results: [],
      history: [],
      facets: [],
      histTotal: 0,
      histLimit: 20,
      histOffset: 0,
      histSpeaker: '',
      editing: '',
      editTags: {},
      purgeFile: false,
      saving: '',
      busy: false,
      doneCount: 0,
      genError: '',
      uploading: false
    }
  },
  components: { TagEditor },
  computed: {
    histPage() { return Math.floor(this.histOffset / this.histLimit) + 1 },
    histPages() { return Math.max(1, Math.ceil(this.histTotal / this.histLimit)) },
    modelsForMethod() {
      return this.models.filter((m) => m.method === this.method)
    },
    countByMethod() {
      const t = {}
      for (const m of this.models) t[m.method] = (t[m.method] || 0) + 1
      return t
    },
    currentChar() {
      return this.store.characters.find((c) => c.label === this.speakerLabel)
    },
    currentCharName() {
      return this.currentChar ? this.currentChar.name : this.speakerLabel || '角色'
    },
    firstLineOfSpeaker() {
      const seg = this.store.segments.find((s) => this.currentChar && s.speaker === this.currentChar.id)
      return seg ? seg.text : ''
    },
    allVoiceTpls() {
      const seen = new Set(VOICE_TEMPLATES.map((t) => t.text))
      return VOICE_TEMPLATES.concat(this.libVoices.filter((t) => !seen.has(t.text)))
    }
  },
  async created() {
    this.speakerLabel = this.store.characters.length ? this.store.characters[0].label : null
    this.fillSample()
    try { this.models = await api.voiceLabModels() } catch (e) { toast(`模型列表加载失败：${e.message}`, 'err') }
    try { this.styleOptions = await api.emotions() } catch { toast('情感词表加载失败，风格指令仍可手写', 'warn') }
    try { await this.loadHistory(0) } catch { /* 历史非关键路径 */ }
    try { this.facets = (await api.vaultSchema()).facets } catch { toast('标签词表加载失败，标注不可用', 'warn') }
    try { this.cloneList = await api.cloneVoices() } catch { this.cloneList = [] }
    this.fetchTpls()
  },
  watch: {
    speakerLabel() { this.fillSample() },
    method(k) {
      this.picked = this.models.filter((m) => m.method === k && m.available).slice(0, 1).map((m) => m.key)
    }
  },
  methods: {
    switchMethod(k) { this.method = k },
    async loadHistory(offset) {
      this.histOffset = Math.max(0, offset || 0)
      this.editing = ''
      try {
        const r = await api.voiceLabHistory({ limit: this.histLimit, offset: this.histOffset, speaker: this.histSpeaker })
        this.history = r.records
        this.histTotal = r.total
      } catch (e) { toast(`历史加载失败：${e.message}`, 'err') }
    },
    openTag(r) {
      this.editing = r.id
      this.editTags = Object.assign({}, r.tags || {})
    },
    async saveTags(r) {
      this.saving = r.id
      try {
        const hit = await api.voiceLabRecordUpdate({ id: r.id, tags: this.editTags })
        Object.assign(r, hit)
        this.editing = ''
        toast('标注已保存', 'ok')
      } catch (e) {
        toast(`标注失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    async patchText(r, text) {
      if (text === r.sample_text) return
      this.saving = r.id
      try {
        Object.assign(r, await api.voiceLabRecordUpdate({ id: r.id, text }))
        toast('文本已修改', 'ok')
      } catch (e) {
        toast(`修改失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    async renameRec(r) {
      const cur = r.name || ''
      const name = window.prompt('给这条声音起个标题（留空 = 恢复显示模型名）', cur)
      if (name === null) return
      this.saving = r.id
      try {
        Object.assign(r, await api.voiceLabRecordUpdate({ id: r.id, name: name.trim() }))
        toast(name.trim() ? `✓ 标题已改为「${name.trim()}」` : '已恢复模型名显示', 'ok')
      } catch (e) {
        toast(`改名失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    async dropRecord(r) {
      const extra = this.purgeFile ? '，并删掉它的音频文件' : '（音频文件保留）'
      if (!window.confirm(`删除「${r.model_label} / seed ${r.seed}」这条记录${extra}？`)) return
      this.saving = r.id
      try {
        await api.voiceLabRecordDelete({ id: r.id, purge: this.purgeFile })
        this.history = this.history.filter((x) => x.id !== r.id)
        this.histTotal -= 1
        toast(this.purgeFile ? '记录与音频已删除' : '记录已删除', 'ok')
      } catch (e) {
        toast(`删除失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    async toVault(r) {
      this.saving = r.id
      try {
        const row = await api.vaultAdd({ kind: 'lab', src: r.id, role: r.speaker || this.speakerLabel || '', tags: r.tags || {} })
        toast(`✓ 已存入仓库 #${row.id}（实测 ${row.derived.duration_s}s · ${row.derived.cps} 字/秒）`, 'ok')
      } catch (e) {
        toast(`入库失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    applyVoiceTpl() {
      if (this.voiceTpl !== '') { this.description = this.allVoiceTpls[this.voiceTpl].text; this.voiceTpl = '' }
    },
    async fetchTpls() {
      try {
        const t = await api.voiceTemplates()
        this.libVoices = t.filter((x) => x.kind === 'voice')
        this.libEmotions = t.filter((x) => x.kind === 'emotion')
      } catch { /* 模板库接口未部署时只留预置，不拦人 */ }
    },
    async saveAsTpl(kind, text) {
      const t = (text || '').trim()
      if (!t) { toast('先把描述/指令写好，再存为模板', 'warn'); return }
      const name = window.prompt('模板名', t.slice(0, 18))
      if (!name) return
      try {
        await api.voiceTemplateSave({ kind, name, text: t })
        await this.fetchTpls()
        toast(`✓ 已存为${kind === 'voice' ? '音色' : '情绪'}模板「${name}」`, 'ok')
      } catch (e) { toast(`存模板失败：${e.message}`, 'err') }
    },
    fillStyle(field, text) { if (text) this[field] = text },
    fillSample() {
      if (!this.sampleText && this.firstLineOfSpeaker) this.sampleText = this.firstLineOfSpeaker
    },
    async onRefFile(ev) {
      const file = ev.target.files[0]
      this.uploading = true
      try {
        const r = await api.cloneVoiceUpload(file)
        this.cloneList = await api.cloneVoices()
        this.refAudio = r.filename
        toast('参考音频已上传并选中', 'ok')
        try {
          const asr = await api.transcribeRef(file)
          if (asr.text) {
            this.refText = asr.text
            // ASR 情感标签只在风格指令为空时填入，不覆盖手工选择
            const emo = asr.instruct || (asr.emotion ? asr.emotion.toLowerCase() : '')
            if (emo && !this.description) this.description = emo
            toast(`ref_text 已自动转写${emo ? `（情感：${emo}，已填入风格指令）` : ''}`, 'ok')
          } else {
            toast('ASR 未识别到文本，请手工填写 ref_text', 'warn')
          }
        } catch (e2) {
          toast(`自动转写失败，请手工填写：${e2.message}`, 'warn')
        }
      } catch (e) {
        toast(`上传失败：${e.message}`, 'err')
      } finally {
        this.uploading = false
        ev.target.value = ''
      }
    },
    async generate() {
      if (this.store.mode !== 'live') { toast('演示模式：后端未连接', 'warn'); return }
      if (!this.sampleText.trim()) { toast('请填写试听文本', 'warn'); return }
      this.busy = true
      this.doneCount = 0
      this.genError = ''
      this.results = []
      for (const key of this.picked) {
        try {
          const rec = await api.voiceLabGenerate({
            model: key,
            method: this.method,
            sample_text: this.sampleText,
            description: this.description,
            ref_audio: this.refAudio,
            ref_text: this.refText,
            voice: this.voice,
            instruct: this.instruct,
            seed: this.seed,
            speaker: this.speakerLabel || ''
          })
          this.results.push(rec)
        } catch (e) {
          this.genError = `${key} 生成失败：${e.message}`
          break
        } finally {
          this.doneCount++
        }
      }
      this.busy = false
      try { this.history = (await api.voiceLabHistory()).records.slice(0, 20) } catch { /* ignore */ }
      if (!this.genError && this.results.length) toast(`${this.results.length} 条试听已生成`, 'ok')
    },
    boundCharOf(r) {
      const path = r.method === 'design' ? String(r.audio_url || '').replace(/^\//, '')
        : r.method === 'clone' ? `clone_voices/${r.ref_audio}` : ''
      return this.store.characters.find((c) => {
        const cfg = c.config
        if (!cfg) return false
        if (r.method === 'custom') return cfg.type === 'custom' && cfg.voice === r.voice
        return !!path && cfg.type === 'clone' && cfg.ref_audio === path
      })
    },
    isUsed(r) { return !!this.boundCharOf(r) && !this.unlocked.includes(r.id) },
    useOrUnlock(r) {
      if (this.isUsed(r)) {
        const name = this.boundCharOf(r).name
        this.unlocked.push(r.id)
        toast(`已解除「${name}」的占用标记，现在可选给其他角色（${name} 的原绑定本身未改动）`, 'warn')
        return
      }
      this.apply(r)
    },
    async apply(r) {
      if (!this.speakerLabel) { toast('先选择目标角色', 'warn'); return }
      // 串绑防护：这条声音当时是给别的角色造的，绑到当前角色前必须二次确认
      if (r.speaker && r.speaker !== this.speakerLabel) {
        const from = this.store.characters.find((c) => c.label === r.speaker)
        if (!window.confirm(`这条声音是给「${from ? from.name : r.speaker}」造的，确定绑给「${this.currentCharName}」？`)) return
      }
      const eng = r.engine || 'qwen'   // 服务端回传实际出声引擎，批量生成据此分发
      this.applying = r.id
      let cfg
      if (r.method === 'design') {
        cfg = {
          type: 'clone', voice: null, engine: eng,
          ref_audio: r.audio_url.replace(/^\//, ''),
          ref_text: r.sample_text,
          description: r.description, character_style: r.description,
          seed: -1, source_model: r.model_label
        }
      } else if (r.method === 'clone') {
        cfg = {
          type: 'clone', voice: null, engine: eng, mode: r.mode || 'zero_shot',
          ref_audio: `clone_voices/${r.ref_audio}`,
          ref_text: r.ref_text,
          description: '', character_style: r.description,
          seed: -1, source_model: r.model_label
        }
      } else {
        cfg = {
          type: 'custom', voice: r.voice, engine: eng,
          default_style: r.instruct, character_style: r.instruct,
          seed: -1, source_model: r.model_label
        }
      }
      try {
        // 只认当前选中的目标角色：r.speaker 是「生成时」的标签，拿它当绑定对象会把声音写进别的角色
        const ok = await actions.saveVoiceConfig({ [this.speakerLabel]: cfg })
        if (ok) {
          this.unlocked = this.unlocked.filter((x) => x !== r.id)
          toast(`✓ 已绑定「${this.currentCharName}」← ${r.model_label}（引擎 ${eng}）。旧音频不会自动变，去「角色与声音」点「重生成该角色台词」`, 'ok')
        } else toast('绑定失败：后端未保存，见右上角错误', 'err')
      } finally {
        this.applying = ''
      }
    }
  }
}
</script>

<style scoped>
.layout { display: grid; grid-template-columns: 1fr 1.35fr; gap: 16px; align-items: start; }
.col { padding: 0 0 12px; overflow: hidden; }
.col-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--line);
}
.hist-head { border-top: 1px solid var(--line); margin-top: 10px; }
.hist-tools { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.hist-tools select { font-size: 12px; padding: 3px 6px; }
.purge { display: flex; align-items: center; gap: 4px; color: var(--t2); }
.hist-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
.hist-tags.editing { display: block; }
.chip-dim { background: var(--bg3); color: var(--t2); }
.field { padding: 12px 16px 0; }
.tpl { width: 100%; margin-bottom: 6px; }
.btn-used { background: var(--red); border-color: var(--red); color: #fff; }
.tabs { display: flex; gap: 6px; margin-top: 6px; }
.tab {
  padding: 6px 14px; border: 1px solid var(--line2); background: var(--bg2);
  color: var(--t2); border-radius: 8px; cursor: pointer; font-size: 13px;
}
.tab.on { background: var(--accent-dim); border-color: var(--accent); color: var(--accent); font-weight: 700; }
.tab-n { font-size: 11px; opacity: 0.65; margin-left: 5px; }
.hint { font-size: 11.5px; color: var(--t3); margin-top: 6px; }
.model-box { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.model-item { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
.model-name { font-weight: 600; }
.chip-ok { background: rgba(74, 222, 128, 0.12); color: var(--green); }
.chip-off { background: var(--bg3); color: var(--t3); }
.gen-btn { width: 100%; justify-content: center; margin-top: 10px; }
.btn-sm { padding: 3px 10px; font-size: 12px; }

.result-row {
  display: flex; flex-direction: column; gap: 8px;
  padding: 12px 16px; border-bottom: 1px solid var(--line);
}
.hist-row { opacity: 0.9; }
.r-model { font-weight: 700; display: flex; align-items: baseline; gap: 8px; }
.r-time { font-size: 11.5px; color: var(--t3); font-weight: 400; }
.r-line { font-size: 12px; margin-top: 4px; }
.r-text { width: 100%; margin-top: 4px; font-size: 12px; color: var(--t1); background: var(--bg2); border: 1px solid var(--line); border-radius: 6px; padding: 4px 6px; resize: vertical; }
.r-desc { font-size: 12px; color: var(--t2); margin-top: 2px; }
.r-acts { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.r-acts audio { flex: 1; height: 34px; min-width: 0; }
.ref-play audio { width: 100%; height: 34px; margin-top: 8px; }
.err-box { margin: 12px 16px; padding: 10px 12px; border-radius: 8px; font-size: 12.5px;
  background: rgba(248, 113, 113, 0.12); color: var(--red, #f87171); }
.lib-empty { padding: 24px 16px; font-size: 12.5px; }
.apply-mask {
  position: fixed; inset: 0; z-index: 60;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  background: rgba(8, 11, 18, 0.62); backdrop-filter: blur(2px);
}
.apply-txt { font-size: 13px; color: var(--t1); }
.spin {
  width: 34px; height: 34px; border-radius: 50%;
  border: 3px solid var(--line2); border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.mask-enter-active, .mask-leave-active { transition: opacity 0.25s ease; }
.mask-enter-from, .mask-leave-to { opacity: 0; }
</style>
