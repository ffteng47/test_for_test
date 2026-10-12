<template>
  <footer class="transport">
    <button class="play" @click="onPlay">
      <span v-if="!playing">▶</span><span v-else>❚❚</span>
    </button>
    <div class="now">
      <div class="now-head">
        <span class="chip spk" :style="spkStyle">{{ cur ? cur.name : '—' }}</span>
        <span class="mono pos">{{ curIdx + 1 }} / {{ segs.length }}</span>
      </div>
      <div class="now-text" :class="{ marquee: playing }">{{ cur ? cur.text : '' }}</div>
    </div>
    <div class="wave" v-if="!auditOn">
      <i v-for="(s, i) in segs" :key="s.id"
         :style="{ height: 6 + (s.text.length % 22) + 'px',
                   background: i === curIdx ? 'var(--accent)' : (s.status==='error' ? 'var(--red)' : i < curIdx ? 'var(--teal)' : 'var(--bg3)') }"
         @click="select(i)"></i>
    </div>
    <div class="audit" v-else>
      <button v-for="(v, i) in VERDICT_ORDER" :key="v" class="btn btn-xs vd"
              :class="{ picked: curSeg && curSeg.listen === v }"
              :title="VERDICT_HELP[v]" @click="verdict(v)">{{ i + 1 }} {{ VERDICT_ICON[v] }} {{ VERDICT[v] }}</button>
      <span class="mono a-prog" :title="'本段已听 ' + auditSecs + ' s；判定落本书 prooflisten.jsonl，重听以最后一条为准'">
        {{ listenRep ? listenRep.已审段数 + ' / ' + listenRep.总段数 : '—' }}
      </span>
      <span class="a-help dim">空格 重听 · 1–4 判定 · n/b 下/上一段 · Esc 退出</span>
    </div>
    <div class="time mono">{{ fmt(elapsed) }} <span class="t-dim">/ {{ fmt(total) }}</span></div>
    <div class="actions">
      <button class="btn btn-xs" :class="{ on: auditOn }" :disabled="auditBlocked"
              :title="auditBlocked ? '审听端点未就绪（/api/prooflisten）' : '逐段连播 + 四类判定：出错率 / 工时比 / 返工率三个数的唯一来源，机检替代不了'"
              @click="toggleAudit">{{ auditOn ? '◉ 审听中' : '◎ 审听' }}</button>
      <button class="btn btn-ghost btn-xs" :disabled="busyAudio" @click="regen(curIdx)">{{ busyAudio ? '生成中…' : '重生成本句' }}</button>
    </div>
  </footer>
</template>

<script>
import { store, speakerOf, fmtTime, toast, VERDICT, VERDICT_ICON, VERDICT_ORDER, VERDICT_HELP } from '../data/store.js'
import { actions } from '../api/actions.js'
import { toggleUrl, playUrl } from '../audio/player.js'

// 审听状态留在本组件：TransportBar 全生命周期只挂载一次，判定键也只在这里。
export default {
  data() {
    return { store, fake: false, VERDICT, VERDICT_ICON, VERDICT_ORDER, VERDICT_HELP, timer: 0, audit: { on: false, t0: 0, now: 0 } }
  },
  computed: {
    live() { return this.store.mode === 'live' },
    busyAudio() { return !!this.store.busy.audio },
    playing() { return this.live ? this.store.transport.playing : this.fake },
    auditOn() { return this.audit.on },
    auditBlocked() { return this.live && !this.store.system.listen },
    auditSecs() { return this.audit.on ? Math.max(0, Math.round((this.audit.now - this.audit.t0) / 1000)) : 0 },
    listenRep() { return this.store.system.listen },
    segs() { return this.store.segments },
    // 跟随剧本工作台/波形点击选中的段（store.transport.segId 为唯一游标）
    curIdx() {
      const i = this.segs.findIndex((s) => s.id === this.store.transport.segId)
      return i >= 0 ? i : 0
    },
    curSeg() { return this.segs[this.curIdx] },
    cur() {
      if (!this.curSeg) return null
      return { name: speakerOf(this.curSeg.speaker).name, text: this.curSeg.text }
    },
    curSpeaker() { return speakerOf(this.curSeg ? this.curSeg.speaker : 'narrator') },
    spkStyle() { return { background: this.curSpeaker.color + '22', color: this.curSpeaker.color } },
    elapsed() { return this.live ? this.store.transport.elapsed : 96000 },
    total() {
      if (this.live) return this.store.transport.duration
      return this.segs.reduce((a, s) => a + s.duration, 0)
    }
  },
  watch: {
    'store.transport.segId'(id) {
      // 工作台/审听改选别的段时，若正在播放跟着走。用 playUrl 不用 toggleUrl：
      // 同 src 下 toggle 会把它刚开播的这一段又按停。
      const seg = this.segs.find((s) => s.id === id)
      if (this.live && this.store.transport.playing && seg && seg.audioPath) playUrl(seg.audioPath, seg.id)
    }
  },
  methods: {
    fmt: fmtTime,
    srcOf(seg) { return seg && seg.audioPath ? seg.audioPath : (this.live ? '/api/audiobook' : '') },
    onPlay() {
      if (!this.live) { this.fake = !this.fake; return }
      const seg = this.curSeg
      if (!seg) { toast('没有可播放的段', 'warn'); return }
      if (!seg.audioPath) { toast('本段尚未生成，改播成品整书', 'warn') }
      toggleUrl(this.srcOf(seg), seg.id)
    },
    select(i) {
      if (this.segs[i]) this.store.transport.segId = this.segs[i].id
      if (this.live && this.segs[i] && this.segs[i].audioPath) toggleUrl(this.segs[i].audioPath, this.segs[i].id)
    },
    regen(idx) { actions.generateChunk(idx) },
    toggleAudit() {
      this.audit.on = !this.audit.on
      if (this.audit.on) {
        this.audit.t0 = this.audit.now = Date.now()
        this.timer = setInterval(() => { this.audit.now = Date.now() }, 1000)
        toast('审听中：空格重听本段，1/2/3/4 判定后自动连播下一段，Esc 退出', 'warn')
      } else {
        clearInterval(this.timer)
      }
    },
    async verdict(k) {
      const seg = this.curSeg
      if (!seg) return
      const secs = (Date.now() - this.audit.t0) / 1000
      this.audit.t0 = Date.now()
      if (await actions.listenVerdict(seg.id - 1, k, secs)) this.jump(1)
    },
    // n / 判定后都要落到「下一段有音频的」，否则连播会停在空段上
    jump(dir) {
      for (let i = this.curIdx + dir; i >= 0 && i < this.segs.length; i += dir) {
        const s = this.segs[i]
        if (s.audioPath) {
          this.store.transport.segId = s.id
          playUrl(s.audioPath, s.id)
          return
        }
      }
      if (dir > 0) toast('后面没有已生成的段了', 'warn')
    },
    onKey(e) {
      if (!this.auditOn || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return
      const map = { 1: 'ok', 2: 'misread', 3: 'timbre', 4: 'regen' }
      if (map[e.key]) { e.preventDefault(); this.verdict(map[e.key]) }
      else if (e.key === 'n') { e.preventDefault(); this.jump(1) }
      else if (e.key === 'b') { e.preventDefault(); this.jump(-1) }
      else if (e.key === ' ') { e.preventDefault(); this.onPlay() }
      else if (e.key === 'Escape') this.toggleAudit()
    }
  },
  mounted() { document.addEventListener('keydown', this.onKey) },
  beforeDestroy() {
    document.removeEventListener('keydown', this.onKey)
    if (this.timer) clearInterval(this.timer)
  }
}
</script>

<style scoped>
.transport {
  grid-area: trans;
  background: var(--bg1);
  border-top: 1px solid var(--line);
  display: flex; align-items: center; gap: 12px;
  padding: 0 20px;
}
.play {
  width: 42px; height: 42px; border-radius: 50%; flex: none;
  background: var(--accent); border: none; color: #fff;
  font-size: 14px; cursor: pointer;
  box-shadow: 0 0 18px rgba(124, 108, 255, 0.4);
}
.now { min-width: 260px; max-width: 360px; }
.now-head { display: flex; align-items: center; gap: 8px; }
.spk { font-size: 11px; }
.pos { font-size: 11px; color: var(--t3); margin-left: auto; }
.now-text {
  font-size: 12.5px; color: var(--t2); margin-top: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.wave { flex: 1; display: flex; align-items: center; gap: 3px; height: 42px; overflow: hidden; }
.wave i {
  flex: 1; min-width: 3px; max-width: 9px; border-radius: 2px;
  background: var(--bg3); cursor: pointer; transition: background 0.2s;
}
.t-dim { color: var(--t3); }
.time { font-size: 12px; color: var(--t2); }
.actions { display: flex; gap: 8px; }
.btn-xs { padding: 5px 10px; font-size: 12px; white-space: nowrap; }
.actions .btn.on { border-color: var(--teal); color: var(--teal); background: rgba(52, 214, 198, 0.1); }
.audit { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; }
.vd.picked { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }
.a-prog { font-size: 12px; color: var(--t2); white-space: nowrap; }
.a-help { font-size: 11px; white-space: nowrap; }
</style>
