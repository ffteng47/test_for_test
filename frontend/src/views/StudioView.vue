<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">生成车间</div>
        <div class="view-sub">单 GPU Worker · 逐段生成 · 断点续跑 · 失败段只重做缺失音频</div>
      </div>
      <div class="head-actions">
        <button class="btn" :class="{ 'btn-stop': paused }" @click="toggleQueue">
          {{ paused ? '▶ 恢复队列' : '⏸ 暂停队列' }}
        </button>
        <button class="btn btn-primary" :disabled="audioBusy" @click="batch">
          {{ audioBusy ? `◌ 生成中${audioProg}` : '＋ 批量生成' }}
        </button>
      </div>
    </div>

    <div class="stat-row">
      <div class="stat card">
        <div class="label">GPU 显存</div>
        <div class="stat-num">{{ store.system.gpuUsed }}<span class="stat-unit">/ {{ store.system.gpuTotal }} GB</span></div>
        <div class="meter"><i :style="{ width: (store.system.gpuUsed / store.system.gpuTotal * 100) + '%' }"></i></div>
        <div class="stat-note dim">含 mineru 常驻 6.8GB · TTS 独占加载</div>
      </div>
      <div class="stat card">
        <div class="label">当前任务</div>
        <div class="stat-num t-accent">{{ running ? '#' + running.id : '—' }}</div>
        <div class="stat-note dim">{{ running ? running.name : '队列空闲' }}</div>
      </div>
      <div class="stat card">
        <div class="label">待生成段</div>
        <div class="stat-num">{{ pendingSegs }}</div>
        <div class="stat-note dim">跨 {{ pendingChapters }} 个章节</div>
      </div>
      <div class="stat card">
        <div class="label">失败段</div>
        <div class="stat-num t-err">{{ failedSegs }}</div>
        <div class="stat-note dim">自动重试 ≤ 3 次后转人工</div>
      </div>
    </div>

    <div class="grid2">
      <!-- 任务队列 -->
      <div class="card panel">
        <div class="panel-head">
          <span class="label">JOB QUEUE · 调度记录</span>
          <span class="chip" :class="paused ? 'chip-paused' : 'chip-live'">{{ paused ? '已暂停' : '调度中' }}</span>
        </div>
        <div v-for="j in store.jobs" :key="j.id" class="job-row">
          <span class="job-type" :class="'jt-' + j.type">{{ typeLabel(j.type) }}</span>
          <div class="job-main">
            <div class="job-name">
              <span class="mono dim">#{{ j.id }}</span> {{ j.name }}
            </div>
            <div class="prog"><i :style="{ width: j.progress + '%' }" :class="'pg-' + j.status"></i></div>
            <div class="job-meta">
              <span>{{ j.progress }}%</span>
              <span v-if="j.total" class="mono">{{ j.done }}/{{ j.total }} · 剩 {{ remain(j) }}<template v-if="j.failed"> · 失败 {{ j.failed }}</template></span>
              <span v-if="j.eta" class="mono">ETA {{ j.eta }}</span>
              <span :class="statusCls(j.status)">{{ statusText(j.status) }}</span>
            </div>
            <div v-if="j.status === 'running' && j.logs && j.logs.length" class="job-log mono">
              {{ j.logs[j.logs.length - 1] }}
            </div>
          </div>
          <button v-if="j.status === 'running'" class="btn btn-ghost btn-xs" @click="cancel(j)">取消</button>
        </div>
        <div class="panel-foot dim">
          任务状态落 SQLite（<span class="mono">generation_jobs</span>），Redis 只做短期进度快照；重启后 stale 任务自动回收。
        </div>
      </div>

      <!-- 章节矩阵 -->
      <div class="card panel">
        <div class="panel-head">
          <span class="label">CHAPTERS · 生成状态</span>
          <button class="btn btn-ghost btn-xs" @click="retryFailed">重试全部失败段</button>
        </div>
        <div class="ch-table">
          <div class="ch-head-row">
            <span>章节</span><span>标注</span><span>音频</span><span>质检</span><span></span>
          </div>
          <div v-for="ch in store.chapters" :key="ch.id" class="ch-row">
            <div class="ch-title">{{ ch.title }}</div>
            <div><span class="dotst" :class="ch.status !== 'pending' ? 'ok' : 'idle'"></span></div>
            <div><span class="dotst" :class="audioDot(ch.status)"></span></div>
            <div><span class="dotst" :class="qcDot(ch.status)"></span></div>
            <div class="ch-acts">
              <button
                v-if="ch.status === 'annotated'"
                class="btn btn-xs"
                @click="genChapter(ch)"
              >生成</button>
              <button
                v-else-if="ch.status === 'generated'"
                class="btn btn-xs btn-ghost"
                @click="$router.push('/script')"
              >复审</button>
              <span v-else class="dim ch-wait">待标注</span>
            </div>
          </div>
        </div>
        <div class="panel-foot dim">
          幂等命名：<span class="mono">[index][hash][model][voice][fail]</span> —— 重复提交不会产生重复音频。
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { store } from '../data/store.js'
import { actions } from '../api/actions.js'
import { remain } from '../data/progress.js'

export default {
  name: 'StudioView',
  data() {
    return { store, paused: false }
  },
  computed: {
    running() {
      return this.store.jobs.find(j => j.status === 'running')
    },
    // 批量生成按钮态跟随顶栏 audio 任务（同 CastView）：跨刷新/跨标签也知道自己「在跑」
    audioJob() {
      return this.store.jobs.find(x => x.task === 'audio' && x.status === 'running')
    },
    audioBusy() {
      return !!this.store.busy.audio || !!this.audioJob
    },
    audioProg() {
      const j = this.audioJob
      return j && j.total ? ` ${j.done}/${j.total}` : '…'
    },
    pendingSegs() {
      return this.store.segments.filter(s => s.status === 'pending' || s.status === 'generating').length
    },
    pendingChapters() {
      return this.store.chapters.filter(c => c.status !== 'pending').length
    },
    failedSegs() {
      return this.store.segments.filter(s => s.status === 'error').length
    }
  },
  methods: {
    remain,
    typeLabel(t) {
      return { tts: 'TTS', annotate: '标注', qc: '质检', persona: '音色', export: '导出' }[t] || t
    },
    statusCls(s) {
      return { running: 't-accent', done: 't-ok', warn: 't-warn', failed: 't-err' }[s]
    },
    statusText(s) {
      return { running: '生成中', done: '完成', warn: '有复核项', failed: '失败' }[s]
    },
    audioDot(st) {
      return st === 'generated' ? 'ok' : st === 'annotated' ? 'idle' : 'off'
    },
    qcDot(st) {
      return st === 'generated' ? 'warn' : 'off'
    },
    toggleQueue() {
      this.paused = !this.paused
      if (this.paused) actions.cancelAudio()
    },
    batch() { actions.generatePending() },
    genChapter() { actions.generatePending() },
    retryFailed() { actions.retryFailed() },
    cancel() { actions.cancelAudio() }
  }
}
</script>

<style scoped>
.stat-row {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 14px; margin-bottom: 16px;
}
.stat { padding: 14px 16px; }
.stat-num { font-size: 26px; font-weight: 800; margin-top: 4px; font-family: var(--mono); }
.stat-unit { font-size: 13px; color: var(--t3); font-weight: 500; }
.stat-note { font-size: 11.5px; margin-top: 6px; }
.meter { height: 6px; background: var(--bg3); border-radius: 3px; margin-top: 10px; overflow: hidden; }
.meter i {
  display: block; height: 100%; border-radius: 3px;
  background: linear-gradient(90deg, var(--teal), var(--accent));
}

.grid2 { display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; align-items: start; }
.panel { overflow: hidden; }
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--line);
}
.panel-foot { padding: 12px 16px; font-size: 11.5px; border-top: 1px dashed var(--line); }

.job-row {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-bottom: 1px solid var(--line);
}
.job-type {
  flex: none; width: 44px; text-align: center;
  font-size: 11px; font-weight: 700; padding: 4px 0;
  border-radius: 6px;
}
.jt-tts { background: var(--accent-dim); color: var(--accent); }
.jt-annotate { background: rgba(52, 214, 198, 0.12); color: var(--teal); }
.jt-qc { background: rgba(245, 185, 63, 0.12); color: var(--amber); }
.job-main { flex: 1; min-width: 0; }
.job-name { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.prog { height: 5px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
.prog i { display: block; height: 100%; border-radius: 3px; transition: width 0.4s; }
.pg-running { background: var(--accent); animation: pulse 1.4s infinite; }
.pg-done { background: var(--green); }
.pg-warn { background: var(--amber); }
.pg-failed { background: var(--red); }
@keyframes pulse { 50% { filter: brightness(1.35); } }
.job-meta { display: flex; gap: 14px; font-size: 11.5px; color: var(--t2); margin-top: 5px; }
.job-log { font-size: 10.5px; color: var(--t3); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.ch-table { padding: 4px 16px 8px; }
.ch-head-row, .ch-row {
  display: grid; grid-template-columns: 1fr 48px 48px 48px 76px;
  align-items: center; gap: 8px;
}
.ch-head-row { padding: 10px 0 6px; font-size: 11px; color: var(--t3); letter-spacing: 0.06em; }
.ch-row { padding: 11px 0; border-top: 1px solid var(--line); }
.ch-title { font-weight: 600; font-size: 13px; }
.dotst { display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
.dotst.ok { background: var(--green); }
.dotst.idle { background: var(--amber); }
.dotst.off { background: var(--bg3); border: 1px solid var(--line2); }
.ch-acts { text-align: right; }
.ch-wait { font-size: 11.5px; }

.btn-xs { padding: 3px 10px; font-size: 12px; }
.btn-stop { border-color: var(--amber); color: var(--amber); }
.chip-live { background: rgba(74, 222, 128, 0.12); color: var(--green); }
.chip-paused { background: rgba(245, 185, 63, 0.12); color: var(--amber); }
</style>
