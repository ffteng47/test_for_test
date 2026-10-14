<template>
  <transition name="hud">
    <div v-if="jobs.length" class="hud">
      <div v-for="j in jobs" :key="j.id" class="hud-row">
        <span class="hud-pulse"></span>
        <span class="hud-name">{{ j.name }}</span>
        <div class="hud-track">
          <i :class="{ indet: !j.total }" :style="{ width: (j.total ? pct(j) : 100) + '%' }"></i>
        </div>
        <span class="hud-num mono">
          <template v-if="j.total">
            {{ j.done }}/{{ j.total }}
            <span class="hud-sep">·</span> 剩 {{ remain(j) }}
            <template v-if="j.failed"><span class="hud-sep">·</span><span class="hud-bad">失败 {{ j.failed }}</span></template>
            <span class="hud-sep">·</span>{{ pct(j) }}%
          </template>
          <template v-else>准备中…</template>
        </span>
        <span class="hud-time mono">已跑 {{ elapsed(j) }}<template v-if="eta(j)"> · 预计还需 {{ eta(j) }}</template></span>
        <button v-if="j.task === 'audio'" class="hud-stop" @click="stop">⏹ 停止</button>
      </div>
    </div>
  </transition>
</template>

<script>
import { store } from '../data/store.js'
import { actions } from '../api/actions.js'
import { pct, remain, elapsed, eta } from '../data/progress.js'

export default {
  name: 'TaskHud',
  data: () => ({ store, now: Date.now() }),
  computed: {
    jobs() { return this.store.jobs.filter((j) => j.status === 'running') }
  },
  mounted() {
    this._t = setInterval(() => { this.now = Date.now() }, 1000)
  },
  beforeDestroy() { clearInterval(this._t) },
  methods: {
    pct,
    remain,
    elapsed(j) { return elapsed(j, this.now) },
    eta(j) { return eta(j, this.now) },
    stop() { actions.cancelAudio() }
  }
}
</script>

<style scoped>
.hud {
  position: fixed; top: 56px; left: 0; right: 0; z-index: 45;
  background: linear-gradient(180deg, var(--bg1), var(--bg2));
  border-bottom: 1px solid var(--accent-dim, rgba(124,108,255,.4));
  box-shadow: 0 10px 30px rgba(0,0,0,.5), 0 0 0 1px rgba(124,108,255,.15);
  display: flex; flex-direction: column;
}
.hud-row {
  display: flex; align-items: center; gap: 14px;
  padding: 11px 20px;
}
.hud-row + .hud-row { border-top: 1px solid var(--line); }
.hud-pulse {
  width: 10px; height: 10px; border-radius: 50%; flex: none;
  background: var(--accent); animation: hud-pulse 1.4s ease-out infinite;
}
@keyframes hud-pulse {
  0% { box-shadow: 0 0 0 0 rgba(124,108,255,.55); }
  70% { box-shadow: 0 0 0 9px rgba(124,108,255,0); }
  100% { box-shadow: 0 0 0 0 rgba(124,108,255,0); }
}
.hud-name { font-size: 13px; font-weight: 700; color: var(--t1); white-space: nowrap; }
.hud-track {
  flex: 1; min-width: 120px; height: 8px; border-radius: 999px;
  background: var(--bg3); overflow: hidden; position: relative;
}
.hud-track i {
  display: block; height: 100%; border-radius: 999px; position: relative;
  background: linear-gradient(90deg, var(--teal), var(--accent));
  transition: width 0.9s ease;
  overflow: hidden;
}
.hud-track i::after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent);
  transform: translateX(-100%); animation: hud-shimmer 1.6s linear infinite;
}
.hud-track i.indet::before {
  content: ''; position: absolute; inset: 0;
  background: repeating-linear-gradient(-45deg, transparent 0 8px, rgba(255,255,255,.12) 8px 16px);
  animation: hud-stripes .8s linear infinite;
}
@keyframes hud-shimmer { to { transform: translateX(100%); } }
@keyframes hud-stripes { to { background-position: 22.6px 0; } }
.hud-num { font-size: 12.5px; color: var(--t1); white-space: nowrap; min-width: 190px; text-align: right; }
.hud-sep { color: var(--t3); margin: 0 4px; }
.hud-bad { color: var(--red, #f87171); }
.hud-time { font-size: 11.5px; color: var(--t3); white-space: nowrap; }
.hud-stop {
  font: inherit; font-size: 12px; font-weight: 700; cursor: pointer;
  background: rgba(248,113,113,.14); color: var(--red, #f87171);
  border: 1px solid rgba(248,113,113,.45); border-radius: 999px;
  padding: 4px 14px; transition: all .15s;
}
.hud-stop:hover { background: var(--red, #f87171); color: #fff; }
.hud-enter-active, .hud-leave-active { transition: transform .25s ease, opacity .25s ease; }
.hud-enter-from, .hud-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
