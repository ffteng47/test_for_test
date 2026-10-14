<template>
  <div class="wrap">
    <div class="view-head">
      <div>
        <div class="view-title">剧本工作台 <span class="chapter-tag mono">第二章 · 铜哨</span></div>
        <div class="view-sub">逐句标注：说话人归属 · instruct 情绪指令 · 确认锁定后可批量生成</div>
      </div>
      <div class="head-actions">
        <div class="seg-switch">
          <button v-for="c in chapters" :key="c.id" class="btn btn-ghost" :class="{ cur: c.id === 2 }">{{ c.title.slice(0, 3) }}</button>
        </div>
        <button class="btn" :disabled="busy.script" @click="act('script', actions.generateScript)">{{ busy.script ? '标注中…' : '⟳ 重新标注' }}</button>
        <button class="btn" :disabled="busy.review" @click="act('review', actions.reviewScript)">{{ busy.review ? '复查中…' : '✓ 校验归属' }}</button>
        <button v-if="busy.audio" class="btn btn-stop" @click="stopGenerate">⏹ 停止生成</button>
        <button v-else class="btn btn-primary" @click="askGenerate">▶ 批量生成</button>
      </div>
    </div>

    <div class="cols">
      <div class="card seglist">
        <div class="stats">
          <span><b>{{ segments.length }}</b> 段</span>
          <span class="t-ok">● {{ done }} 已生成</span>
          <span class="t-err">● {{ errors }} 失败</span>
          <span class="dim">○ {{ pending }} 待生成</span>
          <span v-if="fallbacks" class="t-warn" title="这些段没有可用角色音色，由 Kokoro 顶班，不是角色本身的声音">◐ {{ fallbacks }} 兜底</span>
          <span v-if="store.system.listen" :class="store.system.listen.未审段数 ? 't-warn' : 't-ok'"
                :title="`人工工时 ${Math.round(store.system.listen.人工工时s / 60)} min；判定键在底部播放条右侧（◎ 审听）；机检测不到音色漂移与合法异读，这一遍才是报价用的数`">
            ◎ 审听 {{ store.system.listen.已审段数 }}/{{ store.system.listen.总段数 }}<template v-if="store.system.listen.未审段数"> · 未审 {{ store.system.listen.未审段数 }}</template>
          </span>
        </div>

        <div v-for="s in segments" :key="s.id" class="seg" :class="{ sel: s.id === selected, locked: s.status === 'done' }"
             @click="pick(s.id)">
          <div class="seg-idx mono">{{ String(s.order).padStart(2, '0') }}</div>
          <div class="seg-spk">
            <span class="chip" :style="spkStyle(s.speaker)">{{ spkName(s.speaker) }}</span>
          </div>
          <div class="seg-body">
            <div class="seg-text">{{ s.text }}</div>
            <div class="seg-eng" v-if="s.status === 'done' && (s.engine || s.fallback)">
              <span class="eng-chip" :class="{ fb: s.fallback }">{{ s.fallback ? 'Kokoro 兜底 · 非角色音色' : engineLabel(s.engine) }}</span>
            </div>
            <div class="seg-instruct" v-if="expanded === s.id">
              <textarea rows="2" v-model="s.instruct" @change="actions.editChunk(s.id - 1, { instruct: s.instruct })"></textarea>
              <div class="instr-hint">instruct 决定本句语气，TTS 每句独立合成——上下文要写全。</div>
            </div>
          </div>
          <div class="seg-meta mono">
            <span>{{ fmt(s.duration) }}</span>
            <span v-if="s.listen" class="st" :class="s.listen === 'ok' ? 's-done' : 's-err'" :title="VERDICT[s.listen]">{{ VERDICT_ICON[s.listen] }}</span>
            <span class="st" :class="stClass(s.status)" :title="s.status">{{ stIcon(s.status) }}</span>
            <button class="btn btn-ghost mini" @click.stop="expanded = expanded === s.id ? 0 : s.id">⌄</button>
          </div>
        </div>
      </div>

      <aside class="card inspector">
        <div class="ins-head"><span class="label">段详情</span></div>
        <div class="ins-row"><span class="k">说话人</span>
          <span class="chip" :style="spkStyle(curSeg.speaker)">{{ spkName(curSeg.speaker) }}</span></div>
        <div class="ins-row"><span class="k">类型</span><span>{{ curSeg.kind === 'narration' ? '旁白' : '对白' }}</span></div>
        <div class="ins-row" v-if="curSeg.status === 'done'"><span class="k">出声引擎</span>
          <span class="eng-chip" :class="{ fb: curSeg.fallback }">{{ curSeg.fallback ? 'Kokoro 兜底 · 非角色音色' : engineLabel(curSeg.engine) }}</span></div>
        <div class="ins-row col"><span class="k">instruct 指令</span>
          <textarea rows="3" v-model="draft.instruct"></textarea></div>
        <div class="ins-row col"><span class="k">台词/正文</span>
          <textarea rows="3" v-model="draft.text"></textarea></div>
        <div class="ins-row col"><span class="k">原文回链</span>
          <div class="srcline mono">paragraph #142–#144 · L{{ curSeg.order * 11 }}:2</div></div>
        <div class="ins-row"><span class="k">音频版本</span>
          <div class="versions">
            <button v-for="v in curSeg.versions" :key="v" class="ver mono" :class="{ on: v === curSeg.chosen }"
                    @click="curSeg.chosen = v">v{{ v }}</button>
          </div>
        </div>
        <div class="ins-actions">
          <button class="btn" @click="saveDraft">⌾ 保存修改</button>
          <button class="btn" :class="{ on: listening }" :disabled="!curSeg.audioPath" @click="listen">{{ listening ? '❚❚ 停止试听' : '▷ 试听本句' }}</button>
          <button class="btn" :disabled="busy.audio" @click="regen">↻ 重生成</button>
        </div>
        <div class="qc card2">
          <div class="label">质检</div>
          <div :class="curSeg.qc === 'pass' ? 't-ok' : curSeg.qc === 'retry' ? 't-warn' : 'dim'">
            {{ qcText }}
          </div>
          <div v-if="store.system.continuity" class="dim mono" style="margin-top:6px;font-size:11px">
            全卷字级一致率 {{ (store.system.continuity.sim * 100).toFixed(1) }}% · 漏 {{ store.system.continuity.missing }} · 增 {{ store.system.continuity.added }}
          </div>
        </div>
      </aside>
    </div>

    <div v-if="genDlg" class="gmask" @click.self="genDlg = false">
      <div class="gdlg">
        <div class="gdlg-title">批量生成 · 确认</div>
        <div class="gdlg-sub">将对 <b>{{ toGen }}</b> 个未完成段（待生成 + 失败）启动 TTS 合成（已生成的段不动）。生成中可再点顶部「⏹ 停止生成」中止。</div>
        <label class="gdlg-chk"><input type="checkbox" v-model="skipChk" /> 以后不再弹出此确认</label>
        <div class="gdlg-acts">
          <button class="btn btn-ghost" @click="genDlg = false">取消</button>
          <button class="btn btn-primary" @click="runGenerate">开始生成</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { store, speakerOf, engineLabel, fmtTime, VERDICT, VERDICT_ICON } from '../data/store.js'
import { actions } from '../api/actions.js'
import { toggleUrl } from '../audio/player.js'

export default {
  data: () => ({
    store, actions, selected: 4, expanded: 0, draft: { text: '', instruct: '' },
    genDlg: false, skipChk: false,
    VERDICT, VERDICT_ICON
  }),
  computed: {
    segments() { return this.store.segments },
    chapters() { return this.store.chapters },
    curSeg() { return this.segments.find((s) => s.id === this.selected) || this.segments[0] || { speaker: 'narrator', kind: 'narration', instruct: '', text: '', versions: 1, chosen: 1, qc: null, audioPath: null, id: 1 } },
    busy() { return this.store.busy },
    listening() { return this.store.transport.playing && this.store.transport.segId === this.curSeg.id },
    done() { return this.segments.filter((s) => s.status === 'done').length },
    errors() { return this.segments.filter((s) => s.status === 'error').length },
    pending() { return this.segments.filter((s) => s.status === 'pending').length },
    toGen() { return this.segments.filter((s) => s.status !== 'done').length },
    fallbacks() { return this.segments.filter((s) => s.status === 'done' && s.fallback).length },
    qcText() {
      const s = this.curSeg
      if (!s || !s.qc) return '— 未质检'
      if (s.qcErr != null) {
        const cer = (s.qcErr * 100).toFixed(1)
        return s.qc === 'pass' ? `✓ 音频回听一致（CER ${cer}%）` : `⚠ 音频回听差异 CER ${cer}%，待复核`
      }
      if (this.store.system.continuity) return s.qc === 'pass' ? '✓ 原文无损（字级比对）' : '⚠ 与原文存在差异，待复核'
      return s.qc === 'pass' ? '✓ 转录一致' : '⚠ 疑似漏字，待复核'
    }
  },
  watch: {
    curSeg: {
      immediate: true,
      handler(s) { this.draft = { text: s.text, instruct: s.instruct } }
    },
    // 审听判定在底部播放条上跳段时，工作台跟着走
    'store.transport.segId'(id) { if (this.segments.some((s) => s.id === id)) this.selected = id }
  },
  methods: {
    spkName(id) { return speakerOf(id).name },
    engineLabel,
    spkStyle(id) { const c = speakerOf(id).color; return { background: c + '1f', color: c } },
    stIcon(st) { return { done: '●', error: '✕', pending: '○', generating: '◌' }[st] },
    stClass(st) { return { done: 's-done', error: 's-err', pending: 's-pend', generating: 's-run' }[st] },
    fmt: fmtTime,
    act(task, fn) { fn() },
    askGenerate() {
      if (localStorage.getItem('novel.skipGenConfirm') === '1') { actions.generatePending(); return }
      this.skipChk = false
      this.genDlg = true
    },
    runGenerate() {
      if (this.skipChk) localStorage.setItem('novel.skipGenConfirm', '1')
      this.genDlg = false
      actions.generatePending()
    },
    stopGenerate() { actions.cancelAudio() },
    pick(id) { this.selected = id; this.store.transport.segId = id },
    async saveDraft() {
      const ok = await actions.editChunk(this.curSeg.id - 1, { text: this.draft.text, instruct: this.draft.instruct })
      if (ok) this.curSeg.text = this.draft.text
    },
    listen() { if (this.curSeg.audioPath) toggleUrl(this.curSeg.audioPath, this.curSeg.id) },
    regen() { actions.generateChunk(this.curSeg.id - 1) }
  }
}
</script>

<style scoped>
.wrap { min-width: 900px; height: 100%; display: flex; flex-direction: column; }
.btn-stop { background: var(--red); border-color: var(--red); color: #fff; }
.gmask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55); z-index: 60;
  display: flex; align-items: center; justify-content: center;
}
.gdlg {
  width: 380px; background: var(--bg2); border: 1px solid var(--line2);
  border-radius: 12px; padding: 18px;
}
.gdlg-title { font-weight: 700; font-size: 15px; }
.gdlg-sub { font-size: 12.5px; color: var(--t2); line-height: 1.6; margin-top: 8px; }
.gdlg-chk { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--t3); margin-top: 12px; }
.gdlg-acts { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.chapter-tag { font-size: 12px; color: var(--teal); background: rgba(52, 214, 198, 0.1); padding: 3px 10px; border-radius: 999px; vertical-align: middle; margin-left: 6px; }
.seg-switch { display: flex; gap: 2px; margin-right: 6px; }
.seg-switch .cur { background: var(--accent-dim); color: #fff; }
.cols { display: grid; grid-template-columns: 1fr 280px; gap: 18px; flex: 1; min-height: 0; }
/* 两栏各自全高内滚：几百段的列表自带贴手的滚动条（旧版整页滚，滑块在视口最边、拖不动）；
   stats 钉在列表顶，翻到第 800 段也看得到全书计数 */
.seglist { overflow-y: auto; min-height: 0; }
.stats {
  display: flex; gap: 16px; padding: 12px 16px; font-size: 12px;
  border-bottom: 1px solid var(--line); color: var(--t2);
  background: var(--bg1);
  position: sticky; top: 0; z-index: 3;
}
.stats b { color: var(--t1); }
.seg {
  display: grid; grid-template-columns: 34px 88px 1fr 92px;
  gap: 10px; align-items: start;
  padding: 12px 16px; border-bottom: 1px solid var(--line);
  cursor: pointer; transition: background 0.12s;
}
.seg:hover { background: var(--bg2); }
.seg.sel { background: var(--accent-dim); box-shadow: inset 3px 0 0 var(--accent); }
.seg.locked .seg-text::before { content: '✓ '; color: var(--green); }
.seg-idx { color: var(--t3); font-size: 11px; padding-top: 3px; }
.seg-spk .chip { font-size: 11px; white-space: nowrap; }
.seg-text { font-size: 13.5px; line-height: 1.65; }
.seg-instruct { margin-top: 8px; }
.seg-eng { margin-top: 5px; }
.eng-chip {
  display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 5px;
  background: rgba(52, 214, 198, 0.12); color: var(--teal);
}
.eng-chip.fb { background: rgba(245, 185, 63, 0.15); color: var(--amber); font-weight: 700; }
.instr-hint { font-size: 11px; color: var(--t3); margin-top: 4px; }
.seg-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--t3); justify-content: flex-end; padding-top: 2px; }
.mini { padding: 2px 6px; font-size: 11px; }
.s-done { color: var(--green); }
.s-err { color: var(--red); }
.s-pend { color: var(--t3); }
.s-run { color: var(--amber); animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.3; } }
.inspector { padding: 16px; overflow-y: auto; min-height: 0; }.ins-head { margin-bottom: 12px; }
.ins-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; font-size: 13px; border-bottom: 1px dashed var(--line); }
.ins-row.col { flex-direction: column; align-items: stretch; gap: 6px; }
.k { color: var(--t3); font-size: 11px; letter-spacing: 0.06em; min-width: 60px; }
.srcline { color: var(--teal); font-size: 11.5px; }
.versions { display: flex; gap: 6px; }
.ver {
  background: var(--bg3); border: 1px solid var(--line2); color: var(--t2);
  border-radius: 6px; padding: 3px 10px; font-size: 11px; cursor: pointer;
}
.ver.on { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }
.ins-actions { display: flex; gap: 8px; margin: 14px 0; }
.ins-actions .btn { flex: 1; justify-content: center; }
.ins-actions .btn.on { border-color: var(--teal); color: var(--teal); background: rgba(52, 214, 198, 0.1); }
.card2 { padding: 12px; background: var(--bg2); font-size: 12.5px; }
.card2 .label { margin-bottom: 6px; display: block; }
</style>
