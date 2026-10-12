<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">音频仓库 · Audio Vault</div>
        <div class="view-sub">确认过的好声音 + 量化标签：人物 × 情节 × 情绪 × 感情 × 语速音高，后续 LLM 按标签直接拣现成声音</div>
      </div>
      <div class="head-actions">
        <span class="chip chip-dim">{{ total }} 条</span>
        <span class="chip chip-dim">向量 {{ layout.length }} 维</span>
      </div>
    </div>

    <div class="card bar">
      <div class="filters">
        <input v-model.trim="f.role" placeholder="人物 role" list="role-list" style="width:120px" />
        <datalist id="role-list">
          <option v-for="c in store.characters" :key="c.id" :value="c.label"></option>
        </datalist>
        <select v-model="f.emotion">
          <option value="">情绪</option>
          <option v-for="e in emotions" :key="e" :value="e">{{ emoLabel(e) }} {{ e }}</option>
        </select>
        <select v-model="f.bond">
          <option value="">感情</option>
          <option v-for="v in facetValues('bond')" :key="v" :value="v">{{ v }}</option>
        </select>
        <select v-model="f.scene">
          <option value="">情节</option>
          <option v-for="v in facetValues('scene')" :key="v" :value="v">{{ v }}</option>
        </select>
        <select v-model="f.timbre">
          <option value="">音色质感</option>
          <option v-for="v in facetValues('timbre')" :key="v" :value="v">{{ v }}</option>
        </select>
        <input v-model.number="f.min_rating" type="number" min="0" max="5" placeholder="≥评级" style="width:82px" />
        <input v-model.trim="f.q" placeholder="文本/备注搜索" style="width:150px" />
        <button class="btn btn-sm" :disabled="loading" @click="load(0)">筛选</button>
        <button class="btn btn-ghost btn-sm" @click="reset">清空</button>
        <span class="rng">
          语速
          <input v-model.number="f.pace_min" type="number" min="0" max="1" step="0.05" placeholder="下" />
          <input v-model.number="f.pace_max" type="number" min="0" max="1" step="0.05" placeholder="上" />
          音高
          <input v-model.number="f.pitch_min" type="number" min="0" max="1" step="0.05" placeholder="下" />
          <input v-model.number="f.pitch_max" type="number" min="0" max="1" step="0.05" placeholder="上" />
        </span>
        <button class="btn btn-sm" :disabled="loading" @click="previewPick">按当前筛选试拣</button>
      </div>
      <div class="pick box" v-if="pick.length">
        <div class="label">LLM 出口 /api/vault/pick 的返回（评级优先，带向量供最近邻）</div>
        <div class="pick-row" v-for="c in pick" :key="'p' + c.id">
          <b>#{{ c.id }} {{ c.role || '—' }}</b>
          <span class="dim mono">{{ c.tag_prompt || '无标签' }}</span>
          <span class="dim">向量 {{ c.vector.length }} 维</span>
        </div>
      </div>
    </div>

    <div class="card add">
      <div class="label">入库（入库即实测时长/字每秒/基频，人工标签优先）</div>
      <div class="filters">
        <select v-model="newRow.kind" style="width:130px">
          <option value="lab">实验室记录</option>
          <option value="chunk">台词段序号</option>
          <option value="file">工作区内文件</option>
        </select>
        <select v-if="newRow.kind === 'lab'" v-model="newRow.src" style="min-width:230px">
          <option value="">— 选择试听记录 —</option>
          <option v-for="r in labRecords" :key="r.id" :value="r.id">{{ r.model_label }} · seed {{ r.seed }} · {{ (r.sample_text || '').slice(0, 14) }}</option>
        </select>
        <input v-else-if="newRow.kind === 'chunk'" v-model.trim="newRow.src" type="number" placeholder="段序号，见剧本工作台" style="width:170px" />
        <input v-else v-model.trim="newRow.src" placeholder="相对工作区路径，如 clone_voices/xxx.wav" style="min-width:260px" />
        <input v-model.trim="newRow.role" placeholder="人物（留空取来源）" style="width:140px" />
        <input v-model.trim="newRow.text" placeholder="台词文本（留空取来源）" style="min-width:200px" />
        <button class="btn btn-primary btn-sm" :disabled="adding" @click="add">
          {{ adding ? '实测中…' : '＋ 存入仓库' }}
        </button>
      </div>
      <div class="hint">外部素材先放进工作区（例如 clone_voices/ 或 voicelines/），再用「工作区内文件」入库；仓库只记路径，不复制文件。</div>
      <div class="hint mono">role 存的是角色 key（不是中文名），可直接绑定的音色才有意义：{{ roleHint }}</div>
      <div class="hint">绑定的目标是**每行自己的「人物」框**（按钮上写的就是它）；页顶那个「人物 role」只是查询条件，不参与绑定。</div>
      <div class="err-box" v-if="addError">{{ addError }}</div>
    </div>

    <div class="card list">
      <div class="col-head">
        <span class="label">条目 · 第 {{ page }}/{{ pages }} 页</span>
        <span class="hist-tools">
          <button class="btn btn-sm" :disabled="offset <= 0" @click="load(offset - limit)">← 上页</button>
          <button class="btn btn-sm" :disabled="offset + limit >= total" @click="load(offset + limit)">下页 →</button>
        </span>
      </div>
      <div class="dim empty" v-if="!rows.length">仓库是空的：去「声音实验室」对满意那条点「存仓库」，或在这里按路径入库。</div>
      <div class="row" v-for="r in rows" :key="r.id">
        <div class="r-meta">
          <div class="r-top">
            <b>#{{ r.id }}</b>
            <span class="chip chip-dim">{{ r.kind }}{{ r.src_id ? ' · ' + r.src_id : '' }}</span>
            <input class="role" v-model.trim="r.role" list="role-list" placeholder="人物" />
            <span class="dim mono">{{ r.tag_prompt || '未标注' }}</span>
            <span class="chip" :class="r.missing ? 'chip-off' : 'chip-ok'">
              {{ r.missing ? '文件缺失' : `${r.derived.duration_s}s · ${r.derived.cps}字/秒 · ${r.derived.f0_hz || '?'}Hz` }}
            </span>
          </div>
          <textarea class="r-text mono" rows="2" v-model="r.text"></textarea>
          <button class="btn btn-ghost btn-sm" @click="openEditor(r)">{{ editing === r.id ? '收起标注' : '标注' }}</button>
          <TagEditor v-if="editing === r.id" :facets="facets" v-model="editTags" />
        </div>
        <div class="r-acts">
          <audio :src="r.audio_url" controls preload="none"></audio>
          <button class="btn btn-sm btn-primary" :disabled="saving === r.id" @click="save(r)">
            {{ saving === r.id ? '保存中…' : '保存' }}
          </button>
          <button class="btn btn-sm" :disabled="saving === r.id" @click="bind(r)">
            {{ saving === r.id ? '绑定中…' : `绑定 → ${r.role || '未填人物'}` }}
          </button>
          <button class="btn btn-sm btn-ghost" :disabled="saving === r.id" @click="drop(r)">删除</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="label">量化说明 · 同一份标签既能喂 LLM（tag_prompt 一句中文），也能喂最近邻（vector 定长）</div>
      <div class="hint mono">{{ layout.join(' | ') }}</div>
      <div class="hint">语速按 {{ bounds.pace_cps[0] }}–{{ bounds.pace_cps[1] }} 字/秒归一化，音高按 {{ bounds.pitch_hz[0] }}–{{ bounds.pitch_hz[1] }}Hz 归一化；情绪取 emotion_map 的 16 个规范值，附效价/唤醒两维。</div>
    </div>

    <transition name="mask">
      <div v-if="mask" class="apply-mask">
        <div class="spin"></div>
        <div class="apply-txt">{{ mask }}</div>
      </div>
    </transition>
  </div>
</template>

<script>
import { store, toast } from '../data/store.js'
import { actions } from '../api/actions.js'
import { api } from '../api/client.js'
import TagEditor from '../components/TagEditor.vue'

const EMPTY_FILTER = { role: '', emotion: '', bond: '', scene: '', timbre: '', q: '', min_rating: 0,
                       pace_min: '', pace_max: '', pitch_min: '', pitch_max: '' }

export default {
  name: 'VaultView',
  components: { TagEditor },
  data() {
    return {
      store,
      facets: [],
      layout: [],
      emotions: [],
      bounds: { pace_cps: [], pitch_hz: [] },
      emoLabels: {},
      f: Object.assign({}, EMPTY_FILTER),
      rows: [],
      total: 0,
      limit: 20,
      offset: 0,
      pick: [],
      loading: false,
      adding: false,
      addError: '',
      labRecords: [],
      newRow: { kind: 'lab', src: '', role: '', text: '' },
      editing: '',
      editTags: {},
      saving: '',
      mask: ''
    }
  },
  computed: {
    page() { return Math.floor(this.offset / this.limit) + 1 },
    pages() { return Math.max(1, Math.ceil(this.total / this.limit)) },
    currentChar() {
      return this.store.characters.find((c) => c.label === this.f.role)
    },
    currentCharName() {
      return this.currentChar ? this.currentChar.name : this.f.role || '角色'
    },
    roleHint() {
      return this.store.characters.length
        ? this.store.characters.map((c) => `${c.label}=${c.name}`).join(' · ')
        : '（角色列表还没加载：先去「角色与声音」）'
    }
  },
  async created() {
    try {
      const s = await api.vaultSchema()
      this.facets = s.facets
      this.layout = s.layout
      this.emotions = s.emotions
      this.bounds = s.bounds
      const emo = s.facets.find((x) => x.key === 'emotion')
      this.emoLabels = (emo && emo.value_labels) || {}
    } catch (e) {
      toast(`标签词表加载失败：${e.message}`, 'err')
    }
    await this.load(0)
    try { this.labRecords = (await api.voiceLabHistory({ limit: 50 })).records } catch (e) {
      this.labRecords = []
      toast(`实验室记录读不到，「按记录入库」暂不可用：${e.message}`, 'warn')
    }
  },
  methods: {
    // 接口往返只有十几毫秒，人眼看不见任何中间态：写操作统一过一层最短 600ms 的蒙版
    async runMasked(text, fn) {
      const t0 = Date.now()
      this.mask = text
      try {
        return await fn()
      } finally {
        const left = 600 - (Date.now() - t0)
        if (left > 0) await new Promise((r) => setTimeout(r, left))
        this.mask = ''
      }
    },
    facetValues(key) {
      const f = this.facets.find((x) => x.key === key)
      return f ? f.values : []
    },
    emoLabel(e) { return this.emoLabels[e] || e },
    cleanFilter() {
      const out = {}
      Object.entries(this.f).forEach(([k, v]) => { if (v !== '' && v !== null && v !== undefined) out[k] = v })
      return out
    },
    async load(offset) {
      this.offset = Math.max(0, offset || 0)
      this.loading = true
      this.editing = ''
      try {
        const r = await api.vaultList(Object.assign(this.cleanFilter(), { limit: this.limit, offset: this.offset }))
        this.rows = r.rows
        this.total = r.total
      } catch (e) {
        toast(`仓库读取失败：${e.message}`, 'err')
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.f = Object.assign({}, EMPTY_FILTER)
      this.pick = []
      this.load(0)
    },
    async previewPick() {
      try {
        this.pick = (await api.vaultPick(Object.assign(this.cleanFilter(), { limit: 3 }))).candidates
        if (!this.pick.length) toast('当前筛选拣不出东西，放宽一档再来', 'warn')
      } catch (e) {
        toast(`试拣失败：${e.message}`, 'err')
      }
    },
    openEditor(r) {
      this.editing = r.id
      this.editTags = JSON.parse(JSON.stringify(r.tags || {}))
    },
    async save(r) {
      this.saving = r.id
      try {
        // 只在标注面板为本行展开时才提交 tags：否则 editTags 是上一行的内容，会写串
        const body = { id: r.id, role: r.role, text: r.text }
        if (this.editing === r.id) body.tags = this.editTags
        const hit = await this.runMasked(`保存仓库条目 #${r.id}…`, () => api.vaultUpdate(body))
        Object.assign(r, hit)
        this.editing = ''
        toast(`✓ #${r.id} 已保存（${hit.tag_prompt || '无标签'}）`, 'ok')
      } catch (e) {
        toast(`保存失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    },
    async add() {
      if (!this.newRow.src) {
        toast(this.newRow.kind === 'lab'
          ? '要先选一条试听记录；下拉里只有占位项说明实验室历史没读到，刷新再看'
          : '要先填来源：台词段序号，或工作区内的相对路径（如 clone_voices/xxx.wav）', 'warn')
        return
      }
      this.adding = true
      this.addError = ''
      try {
        const row = await this.runMasked('实测音频（时长 / 字每秒 / 基频）并入库…', () => api.vaultAdd(Object.assign({}, this.newRow)))
        toast(`✓ 已入库 #${row.id}（${row.derived.cps} 字/秒 · ${row.derived.f0_hz || '基频未定'}Hz）`, 'ok')
        this.newRow.src = ''
        this.newRow.text = ''
        await this.load(0)
      } catch (e) {
        this.addError = e.message
        toast(`入库失败：${e.message}`, 'err')
      } finally {
        this.adding = false
      }
    },
    async bind(r) {
      const role = String(r.role || this.f.role || '').trim()
      if (!role) { toast('这条还没有人物：在行内「人物」框填角色 key（如 NARRATOR）再点绑定', 'warn'); return }
      const ch = this.store.characters.find((c) => c.label === role)
      if (!ch) {
        toast(`「${role}」不是当前书的角色 key，绑了也不会有台词引用它。可用：${this.store.characters.map((c) => c.label).join(' / ') || '（角色列表还没加载，先去「角色与声音」）'}`, 'err')
        return
      }
      this.saving = r.id
      try {
        // 绑定前先把这条的人物落库：否则行内是从筛选框兜底出来的，条目上仍写着别的角色
        if (String(r.role || '').trim() !== role) await api.vaultUpdate({ id: r.id, role })
        const ok = await this.runMasked(`把仓库 #${r.id} 绑定为「${ch.name}」的音色…`, () => actions.saveVoiceConfig({
          // tag_prompt 是量化标签（"语速=0.453，音高=0.079"），只能当段级语气提示用；
          // 塞进 character_style 会被 Qwen clone 路径拼进 instruct 当描述念出来（曾致 CROWD 乱音）。
          // 标签与角色配置的分工见 docs/usage-wiki.md「风格字段各管什么」
          [role]: { type: 'clone', voice: null, engine: '', ref_audio: r.audio_url.replace(/^\//, ''),
                    ref_text: r.text, description: '', character_style: '',
                    seed: -1, source_model: `仓库 #${r.id}` }
        }))
        if (ok) toast(`✓ 「${ch.name}」已绑定仓库 #${r.id}。旧音频不会自己变，去「角色与声音」点「重生成该角色台词」`, 'ok')
      } finally {
        this.saving = ''
      }
    },
    async drop(r) {
      const purge = window.confirm(`删除仓库条目 #${r.id}？\n确定 = 连音频文件一起删（仅限实验室/克隆样本目录内）\n取消 = 只删条目记录`)
      this.saving = r.id
      try {
        await this.runMasked(`删除仓库条目 #${r.id}${purge ? ' 及其音频' : ''}…`, () => api.vaultDelete(r.id, purge))
        this.rows = this.rows.filter((x) => x.id !== r.id)
        this.total -= 1
        toast(`#${r.id} 已删除`, 'ok')
      } catch (e) {
        toast(`删除失败：${e.message}`, 'err')
      } finally {
        this.saving = ''
      }
    }
  }
}
</script>

<style scoped>
.bar, .add, .list { margin-bottom: 14px; }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.filters select, .filters input { font-size: 12px; padding: 4px 6px; }
.rng { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--t2); }
.rng input { width: 56px; }
.pick { margin-top: 10px; }
.pick-row { display: flex; gap: 10px; align-items: baseline; font-size: 12px; padding: 2px 0; }
.row { display: flex; gap: 14px; align-items: flex-start; padding: 12px 0; border-top: 1px solid var(--line); }
.r-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.r-top { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.role { width: 110px; font-size: 12px; padding: 2px 6px; }
.r-text { width: 100%; font-size: 12px; background: var(--bg2); color: var(--t1); border: 1px solid var(--line); border-radius: 6px; padding: 5px 7px; resize: vertical; }
.r-acts { width: 300px; display: flex; flex-direction: column; gap: 8px; }
.r-acts audio { width: 100%; height: 34px; }
.empty { padding: 18px 0; }
.apply-mask {
  position: fixed; inset: 0; z-index: 60;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  background: rgba(8, 11, 18, 0.62); backdrop-filter: blur(2px);
}
.apply-txt { font-size: 13px; color: var(--t1); }
.spin {
  width: 34px; height: 34px; border-radius: 50%;
  border: 3px solid var(--line2); border-top-color: var(--accent);
  animation: vspin 0.8s linear infinite;
}
@keyframes vspin { to { transform: rotate(360deg); } }
.mask-enter-active, .mask-leave-active { transition: opacity 0.2s ease; }
.mask-enter, .mask-leave-to { opacity: 0; }
</style>
