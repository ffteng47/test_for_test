<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">角色与声音</div>
        <div class="view-sub">人物别名归并 · Voice Profile 库 · 角色-声音绑定（换声不必重标全书）</div>
      </div>
      <div class="head-actions">
        <button class="btn btn-ghost" :disabled="importing" @click="importVoice">{{ importing ? '上传中…' : '导入参考音频' }}</button>
        <button class="btn btn-primary" :disabled="store.busy.persona" @click="personaDlg = true">
          {{ store.busy.persona ? '设计中…（见任务队列）' : '⚡ 批量自动设计' }}
        </button>
        <input ref="refInput" type="file" accept=".wav,.mp3,.flac,.ogg" style="display:none" @change="onRefFile" />
      </div>
    </div>

    <div class="layout">
      <!-- 角色列表 -->
      <div class="col card">
        <div class="col-head">
          <span class="label">CAST · 人物表</span>
          <span class="chip chip-dim">{{ store.characters.length }} 人</span>
        </div>
        <div
          v-for="c in store.characters"
          :key="c.id"
          class="cast-row"
          :class="{ active: selected === c.id }"
          @click="selected = c.id"
        >
          <span class="dot" :style="{ background: speakerOf(c.id).color }"></span>
          <div class="cast-main">
            <div class="cast-name">
              {{ c.name }}
              <span v-if="c.id === 'narrator'" class="chip chip-narr">旁白</span>
            </div>
            <div class="cast-sub">
              {{ c.desc }} · 台词 {{ c.lines }} 段
              <span v-if="c.engine && c.engine !== 'qwen'" class="eng-tag">{{ engineLabel(c.engine) }}</span>
            </div>
          </div>
          <span class="bind-state" :class="c.voiceId ? 't-ok' : 't-warn'">
            {{ c.voiceId ? '已绑定' : '未绑定' }}
          </span>
        </div>
      </div>

      <!-- 当前角色详情 -->
      <div class="col card" v-if="current">
        <div class="col-head">
          <span class="label">DETAIL · {{ current.name }}</span>
        </div>

        <div class="field">
          <div class="label">别名 / 称呼归并</div>
          <div class="alias-box">
            <span v-for="a in current.aliases" :key="a" class="chip chip-alias">{{ a }}</span>
            <span v-if="!current.aliases.length" class="dim">无别名（旁白）</span>
            <button class="chip chip-add" @click="addAlias">＋</button>
          </div>
          <div class="hint">speaker_resolver 依据此表把「他 / 少爷 / 晚晚」统一解析到同一 voice_id</div>
        </div>

        <div class="field">
          <div class="label">声音绑定</div>
          <select v-model="binding">
            <option :value="null">— 未绑定 —</option>
            <option v-for="v in store.voices" :key="v.id" :value="v.id">
              {{ v.name }} · {{ v.mode }} · {{ v.model }}
            </option>
          </select>
          <div class="bind-meta" v-if="bindingVoice">
            <span class="chip" :class="bindingVoice.locked ? 'chip-locked' : 'chip-open'">
              {{ bindingVoice.locked ? '🔒 已锁定' : '可覆盖' }}
            </span>
            <span class="mono dim">{{ bindingVoice.id }}</span>
            <span class="dim">样本 {{ bindingVoice.dur }}</span>
          </div>
          <div class="bind-note" :class="bindNote.tone" v-if="bindNote">{{ bindNote.text }}</div>
        </div>

        <div class="field">
          <div class="label">出声引擎</div>
          <select v-model="engine" :disabled="!currentConfig">
            <option v-for="e in engineOptions" :key="e.key" :value="e.key">{{ e.label }}</option>
          </select>
          <div class="hint" v-if="!currentConfig">该角色还没有可保存的音色配置，先在右侧库或「声音实验室」绑定。</div>
          <div class="hint" v-else-if="engineIsFallback">Kokoro 是无参考音频时的兜底档：不能克隆，只出声不扮角，剧本台会逐段标注「兜底」。</div>
          <div class="hint" v-if="currentConfig && engineEmo !== 'verbatim'">{{ engineEmoNote }}</div>
        </div>

        <div class="field" v-if="isCloneEngine">
          <div class="label">出声通道</div>
          <select v-model="channel" :disabled="!currentConfig">
            <option value="zero_shot">纯克隆（音色·语气全部照参考音频）</option>
            <option value="instruct">情感指令（照参考音频的音色 + 每段 instruct）</option>
          </select>
        </div>

        <div class="field" v-if="currentConfig && currentConfig.type === 'clone'">
          <div class="label">参考音频原话 ref_text（纯克隆必填，逐字照抄录音里说的那句）</div>
          <textarea rows="2" v-model="refText" :disabled="!currentConfig"></textarea>
          <div class="hint" v-if="needRefText">⚠ 克隆引擎 + 空 ref_text：批量生成会直接失败。填上参考音频那句话，或把通道改成「情感指令」。</div>
        </div>

        <div class="field two-btns">
          <button class="btn" @click="previewBind">试听当前绑定</button>
          <button class="btn btn-primary" @click="saveBind">保存绑定</button>
        </div>

        <div class="field regen-row">
          <button class="btn" :disabled="!charLines || store.busy.audio" @click="regenChar">
            {{ store.busy.audio ? '生成中…（见任务队列）' : `↻ 重生成该角色台词（${charLines} 段）` }}
          </button>
          <div class="hint">换声只写入绑定，<b>已生成的音频不会自动变</b>——要让新声音生效，必须重跑该角色的段。</div>
        </div>

        <div class="field" v-if="store.mode !== 'live'">
          <div class="label">版本历史</div>
          <div class="vhist">
            <div class="vrow"><span class="mono">bind v3</span><span class="dim">今天 08:55 · 换声 陈默·清隐 ← 旧版</span></div>
            <div class="vrow"><span class="mono">bind v2</span><span class="dim">昨天 21:03 · 首次绑定</span></div>
          </div>
        </div>
      </div>

      <!-- Voice Profile 库 -->
      <div class="col card">
        <div class="col-head">
          <span class="label">VOICE LIBRARY</span>
          <span class="chip chip-dim">{{ store.voices.length }}</span>
        </div>
        <div v-for="v in store.voices" :key="v.id" class="voice-row" :class="{ chosen: binding === v.id }">
          <div class="voice-main">
            <div class="voice-name">
              {{ v.name }}
              <span v-if="v.locked" class="lock">🔒</span>
            </div>
            <div class="voice-sub mono">
              <span :class="'mode-' + v.mode">{{ v.mode }}</span>
              · {{ v.model }} · {{ v.dur }}
            </div>
          </div>
          <div class="voice-acts">
            <button class="btn btn-ghost btn-sm" :disabled="!v.refAudio"
                    :title="v.refAudio ? '试听样本' : '无样本文件，先跑音色设计'" @click="audition(v)">▶</button>
          </div>
        </div>
        <div class="dim lib-empty" v-if="!store.voices.length">
          这本书还没有任何已设计的音色：去「声音实验室」手动选模型造声，或点右上角「⚡ 批量自动设计」。
        </div>
        <div class="lib-foot dim">
          VoiceDesign 产出的声音自动入库；克隆样本存 <span class="mono">data/voices/</span>，带版本与来源。
        </div>
      </div>
    </div>

    <div v-if="personaDlg" class="pmask" @click.self="personaDlg = false">
      <div class="pdlg">
        <div class="pdlg-title">批量自动设计 · 选范围</div>
        <div class="pdlg-sub">LLM 逐角色猜描述 → VoiceDesign 抽预览 → 直接写入 voice_config（会先卸载 TTS 引擎腾显存）。</div>
        <button class="btn pdlg-btn" @click="runPersonas(true)">仅设计未绑定角色（安全，不动已绑定）</button>
        <button class="btn pdlg-btn pdlg-danger" @click="runPersonas(false)">全部人物重新设计 —— 覆盖所有已绑定音色</button>
        <button class="btn btn-ghost pdlg-btn" @click="personaDlg = false">取消</button>
      </div>
    </div>
  </div>
</template>

<script>
import { store, speakerOf, engineLabel, toast } from '../data/store.js'
import { actions } from '../api/actions.js'
import { api } from '../api/client.js'
import { playUrl } from '../audio/player.js'

export default {
  name: 'CastView',
  data() {
    return { store, selected: null, binding: null, engine: '', channel: 'zero_shot', refText: '', importing: false, personaDlg: false }
  },
  computed: {
    current() {
      return this.store.characters.find(c => c.id === this.selected)
    },
    bindingVoice() {
      return this.store.voices.find(v => v.id === this.binding)
    },
    currentConfig() {
      return (this.bindingVoice && this.bindingVoice.config) || (this.current && this.current.config) || null
    },
    engineOptions() {
      return [{ key: '', label: '自动（有可用音色→Qwen3-TTS，缺音色→Kokoro 兜底）' }].concat(this.store.engines)
    },
    engineIsFallback() {
      const row = this.store.engines.find(e => e.key === this.engine)
      return !!(row && row.fallback)
    },
    charLines() {
      return this.current ? this.store.segments.filter(s => s.speaker === this.current.id).length : 0
    },
    isCloneEngine() { return this.engine === 'cosy' || this.engine === 'index' },
    engineEmo() {
      const row = this.store.engines.find(e => e.key === this.engine)
      return (row && row.emo) || 'verbatim'
    },
    engineEmoNote() {
      return {
        verbatim: '段级情感：原样送进模型',
        instruct2: '段级情感：自动包成「用…的语气说话」；选「纯克隆」通道时不读情感',
        emo_vector: '段级情感：sidecar 折成 8 维 emo_vector',
        none: '⚠ 该引擎没有情感通道，每段台词的 instruct 会被忽略'
      }[this.engineEmo]
    },
    needRefText() { return this.isCloneEngine && this.channel === 'zero_shot' && !String(this.refText).trim() },
    // 「保存绑定后，每一句实际会发出什么声音」。音色与试听一致=绿，会跑偏=红。只认 config.type 和引擎，不认显示标签。
    bindNote() {
      const cfg = this.currentConfig
      if (!cfg) return null
      if (this.engineIsFallback) {
        return { tone: 't-err', text: '⚠ Kokoro 不会克隆：每段都是同一个固定朗读声，和试听里的角色音色无关。' }
      }
      if (cfg.type === 'design') {
        return { tone: 't-err', text: '⚠ 描述造声（design）：每一句都按描述重新抽一次音色，30 句就是 30 个不太一样的「他」。要固定：去「声音实验室」对满意的那条点「选用」，它会固化成克隆参考。' }
      }
      if (cfg.type === 'clone') {
        if (!cfg.ref_audio) {
          return { tone: 't-err', text: '⚠ 克隆配置没有参考音频文件，批量生成会失败：导入参考音频或去「声音实验室」重新选用。' }
        }
        if (this.engine === 'cosy' && this.channel === 'zero_shot') {
          return { tone: 't-ok', text: '✓ 纯克隆：音色和语气都锁在这段参考样本上，每句都是试听里那个声音；段级情感不生效（要情绪就切「情感指令」通道）。' }
        }
        if (this.engine === 'cosy' && this.channel === 'instruct') {
        return { tone: 't-ok', text: '✓ 情感指令：音色锁在参考样本上，每段情绪由该段台词的情感指令包成「用…的语气说话」送进模型。' }
      }
      return { tone: 't-ok', text: '✓ 每段都用同一个参考样本出声，就是试听里的那个音色；情绪由每段台词的情感指令提供。' }
      }
      if (cfg.type === 'custom') {
        return { tone: 't-ok', text: `✓ 固定音色「${cfg.voice || '未命名'}」：模型自带的具名说话人，每段一致，参考音频不参与。` }
      }
      return { tone: 't-err', text: `⚠ 未识别的音色类型「${cfg.type}」，无法保证批量出声和试听一致。` }
    }
  },
  created() {
    this.pickInitial()
  },
  watch: {
    selected(id) {
      const c = this.store.characters.find(x => x.id === id)
      this.binding = c ? c.voiceId : null
    },
    currentConfig: {
      immediate: true,
      handler(cfg) {
        this.engine = (cfg && cfg.engine) || ''
        this.refText = (cfg && cfg.ref_text) || ''
        this.channel = (cfg && cfg.mode) || 'zero_shot'
      }
    },
    'store.characters'() {
      if (!this.store.characters.some(c => c.id === this.selected)) this.pickInitial()
    }
  },
  methods: {
    speakerOf,
    engineLabel,
    pickInitial() {
      const first = this.store.characters.find(c => c.voiceId) || this.store.characters[0]
      this.selected = first ? first.id : null
    },
    addAlias() { toast('别名库在 SQLite 阶段落地', 'warn') },
    runPersonas(newOnly) {
      this.personaDlg = false
      actions.generatePersonas({ advanced: false, batch_size: 40, new_only: newOnly })
    },
    importVoice() {
      if (store.mode !== 'live') { toast('演示模式：后端未连接', 'warn'); return }
      this.$refs.refInput.click()
    },
    async onRefFile(ev) {
      const file = ev.target.files[0]
      this.importing = true
      try {
        const r = await api.cloneVoiceUpload(file)
        const ch = this.current
        let asr = { text: '', instruct: '' }
        try {
          asr = await api.transcribeRef(file)
        } catch (e2) {
          toast(`自动转写不可用，需手工填写：${e2.message}`, 'warn')
        }
        const heard = asr.text || ''
        const refText = window.prompt(
          `已上传《${ch ? ch.name : ''}》参考音频。\nASR 已转写以下内容，确认或修正后用于克隆：\n（情感建议：${asr.instruct || '无'}）`,
          heard
        )
        if (refText === null) { toast('已上传但未绑定，可稍后在绑定区保存', 'warn') }
        else if (ch) {
          const ok = await actions.saveVoiceConfig({
            [ch.label]: { type: 'clone', voice: null, engine: this.engine, ref_audio: `clone_voices/${r.filename}`,
                          ref_text: refText, description: '', character_style: asr.instruct || '', seed: -1 }
          })
          if (ok) toast(`参考音频已绑定（引擎 ${this.engine || '自动'}），试听确认后重生成该角色台词`, 'ok')
        } else {
          toast('未选中角色，仅完成上传', 'warn')
        }
      } catch (e) {
        toast(`上传失败：${e.message}`, 'err')
      } finally {
        this.importing = false
        ev.target.value = ''
      }
    },
    regenChar() { actions.generateSpeaker(this.current.id) },
    previewBind() {
      const v = this.bindingVoice
      if (!v) { toast('尚未选择声音绑定', 'warn'); return }
      if (!v.refAudio) { toast(`${v.name} 没有样本文件，先去「声音实验室」造声`, 'warn'); return }
      playUrl(v.refAudio)
    },
    async saveBind() {
      const ch = this.current
      const cfg = this.currentConfig
      if (!ch || !cfg) { toast('缺少可保存的音色配置', 'warn'); return }
      const patchObj = { engine: this.engine, ref_text: this.refText, mode: this.isCloneEngine ? this.channel : '' }
      const next = Object.assign({}, cfg, patchObj)
      const ok = await actions.saveVoiceConfig({ [ch.label]: next })
      if (ok && ch) {
        ch.engine = this.engine
        ch.config = next
        if (this.binding) ch.voiceId = this.binding
      }
    },
    audition(v) {
      this.binding = v.id
      if (v.refAudio) { playUrl(v.refAudio); return }
      toast(`「${v.name}」还没有参考样本，去「声音实验室」造声`, 'warn')
    }
  }
}
</script>

<style scoped>
.pmask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55); display: flex; align-items: center; justify-content: center; z-index: 50; }
.pdlg { background: var(--bg2); border: 1px solid var(--line2); border-radius: 10px; padding: 18px; width: 400px; display: flex; flex-direction: column; gap: 10px; }
.pdlg-title { font-weight: 700; }
.pdlg-sub { font-size: 12px; color: var(--t2); line-height: 1.5; }
.pdlg-btn { justify-content: center; }
.pdlg-danger { background: rgba(240, 102, 95, 0.14); border-color: var(--red); color: var(--red); }
.layout {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1fr;
  gap: 16px;
  align-items: start;
}
.col { padding: 0 0 12px; overflow: hidden; }
.col-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--line);
}
.chip-dim { background: var(--bg3); color: var(--t2); }

.cast-row {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; cursor: pointer;
  border-bottom: 1px solid var(--line);
  transition: background 0.12s;
}
.cast-row:hover { background: var(--bg2); }
.cast-row.active { background: var(--accent-dim); box-shadow: inset 3px 0 0 var(--accent); }
.dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.cast-main { flex: 1; min-width: 0; }
.cast-name { font-weight: 700; display: flex; align-items: center; gap: 8px; }
.cast-sub { font-size: 12px; color: var(--t2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.eng-tag {
  font-size: 10.5px; color: var(--amber); background: rgba(245, 185, 63, 0.12);
  border-radius: 5px; padding: 1px 6px; margin-left: 4px;
}
.bind-state { font-size: 11.5px; font-weight: 600; flex: none; }

.chip-narr { background: rgba(143, 163, 191, 0.14); color: #8fa3bf; }
.chip-alias { background: var(--bg3); color: var(--t1); font-weight: 500; }
.chip-add {
  background: transparent; border: 1px dashed var(--line2);
  color: var(--t3); cursor: pointer;
}
.chip-add:hover { color: var(--accent); border-color: var(--accent); }
.chip-locked { background: rgba(74, 222, 128, 0.12); color: var(--green); }
.chip-open { background: rgba(245, 185, 63, 0.12); color: var(--amber); }

.field { padding: 14px 16px 0; }
.alias-box { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.hint { font-size: 11.5px; color: var(--t3); margin-top: 8px; }
.bind-meta { display: flex; align-items: center; gap: 10px; margin-top: 8px; font-size: 12px; }
.two-btns { display: flex; gap: 8px; }
.two-btns .btn { flex: 1; justify-content: center; }
.regen-row .btn { width: 100%; justify-content: center; }
.vhist { margin-top: 6px; }
.vrow {
  display: flex; gap: 12px; font-size: 12px; padding: 6px 0;
  border-bottom: 1px dashed var(--line);
}
.vrow .mono { color: var(--t2); flex: none; width: 64px; }

.voice-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--line);
  cursor: pointer; transition: background 0.12s;
}
.voice-row:hover { background: var(--bg2); }
.voice-row.chosen { background: var(--accent-dim); }
.voice-name { font-weight: 600; display: flex; align-items: center; gap: 6px; }
.lock { font-size: 11px; }
.voice-sub { font-size: 11.5px; color: var(--t2); margin-top: 2px; }
.mode-design { color: var(--accent); }
.bind-note { font-size: 12px; line-height: 1.55; margin-top: 6px; }
.mode-clone { color: var(--teal); }
.mode-custom { color: var(--amber); }
.btn-sm { padding: 3px 10px; font-size: 12px; }
.lib-foot { padding: 12px 16px 0; font-size: 11.5px; }
.lib-empty { padding: 14px 16px; font-size: 12px; }
</style>
