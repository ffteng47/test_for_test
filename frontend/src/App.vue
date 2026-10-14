<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <div class="logo"></div>
        <div>
          <div class="brand-name">NOVELAUDIO <span>STUDIO</span></div>
          <div class="brand-sub">有声书工作台</div>
        </div>
      </div>
      <div class="project">
        <template v-if="store.mode === 'live' && store.projects.list.length">
          <select class="proj-select" :value="store.projects.active" :disabled="!!switching"
                  @change="onSwitch" title="多本书轮跑：切换工作区（会重启服务）">
            <option v-for="p in store.projects.list" :key="p.slug" :value="p.slug">
              {{ p.title }}（{{ p.segments }} 段）
            </option>
          </select>
          <span v-if="switching" class="chip proj-meta">切换中…</span>
          <button class="proj-add" :disabled="switching" @click="onAddBook" title="新建一本书并自动切换过去">＋ 新书</button>
        </template>
        <template v-else>
          <span class="proj-title">{{ store.project.title }}</span>
          <span class="chip proj-meta">{{ store.project.totalChapters }} 章 · zh</span>
        </template>
      </div>
      <div class="sys">
        <div class="meter">
          <div class="label">VRAM</div>
          <div class="bar"><i :style="{ width: (store.system.gpuUsed / store.system.gpuTotal * 100) + '%' }"></i></div>
          <div class="mono meter-num">{{ store.system.gpuUsed }}/{{ store.system.gpuTotal }}G</div>
        </div>
        <span class="chip status-chip"><i class="dot ok"></i>GPU 就绪</span>
        <span class="chip status-chip"><i class="dot ok"></i>{{ store.system.ollama }}</span>
        <span v-if="store.mode === 'live'" class="chip status-chip mode-live">LIVE</span>
        <span v-else class="chip status-chip mode-demo">演示数据</span>
        <div class="avatar">TFF</div>
      </div>
    </header>

    <TaskHud />

    <nav class="rail">
      <router-link v-for="s in steps" :key="s.path" :to="s.path" class="step" active-class="on">
        <span class="step-no">{{ s.no }}</span>
        <span class="step-name">{{ s.name }}</span>
        <span class="step-tag" v-if="s.tag">{{ s.tag }}</span>
      </router-link>
    </nav>

    <main class="main">
      <transition name="fade" mode="out-in">
        <router-view />
      </transition>
    </main>

    <TransportBar />

    <GlobalLock />

    <transition-group name="toast" tag="div" class="toasts">
      <div v-for="t in store.toast" :key="t.at" class="toast" :class="'k-' + t.kind">{{ t.text }}</div>
    </transition-group>
  </div>
</template>

<script>
import { store, hydrate } from './data/store.js'
import { actions, resyncRunning } from './api/actions.js'
import TransportBar from './components/TransportBar.vue'
import TaskHud from './components/TaskHud.vue'
import GlobalLock from './components/GlobalLock.vue'

export default {
  components: { TransportBar, TaskHud, GlobalLock },
  data() {
    return { store }
  },
  computed: {
    steps() {
      return [
        { no: '01', path: '/import', name: '导入拆解', tag: '' },
        { no: '02', path: '/script', name: '剧本工作台', tag: String(this.store.segments.length) },
        { no: '03', path: '/cast', name: '角色与声音', tag: '' },
        { no: '✚', path: '/voice-lab', name: '声音实验室', tag: '' },
        { no: '◆', path: '/vault', name: '音频仓库', tag: '' },
        { no: '04', path: '/studio', name: '生成车间', tag: this.donePercent ? this.donePercent + '%' : '' },
        { no: '05', path: '/export', name: '母带导出', tag: '' }
      ]
    },
    donePercent() {
      const segs = this.store.segments
      if (!segs.length) return 0
      return Math.round(segs.filter((s) => s.status === 'done').length / segs.length * 100)
    },
    switching() {
      return !!this.store.busy.switch
    }
  },
  methods: {
    async onSwitch(e) {
      const slug = e.target.value
      const ok = await actions.switchProject(slug)
      if (!ok) e.target.value = this.store.projects.active   // 失败回滚选择
    },
    async onAddBook() {
      const title = window.prompt('新书书名（创建空工作区并自动切换过去）')
      if (title && title.trim()) await actions.addProject(title.trim())
    }
  },
  async mounted() {
    const mode = await hydrate()
    if (mode === 'live') {
      // 刷新后进的是任何页面（不只剧本工作台）都要恢复后端在跑的任务与进度
      resyncRunning()
      this._timer = setInterval(() => hydrate(), 15000)
    }
  },
  beforeDestroy() {
    clearInterval(this._timer)
  }
}
</script>

<style scoped>
.app {
  height: 100%;
  display: grid;
  grid-template-columns: 232px 1fr;
  grid-template-rows: 56px 1fr 72px;
  grid-template-areas: "top top" "rail main" "trans trans";
}
.topbar {
  grid-area: top;
  display: flex; align-items: center; gap: 24px;
  padding: 0 20px;
  background: var(--bg1);
  border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; min-width: 190px; }
.logo {
  width: 26px; height: 26px; border-radius: 8px;
  background: conic-gradient(from 210deg, var(--accent), var(--teal), var(--accent));
  box-shadow: 0 0 14px rgba(124, 108, 255, 0.45);
}
.brand-name { font-size: 13px; font-weight: 800; letter-spacing: 0.12em; }
.brand-name span { color: var(--accent); }
.brand-sub { font-size: 10px; color: var(--t3); letter-spacing: 0.2em; }
.project { display: flex; align-items: center; gap: 10px; }
.proj-title { font-weight: 700; font-size: 15px; }
.proj-select {
  font: inherit; font-weight: 700; font-size: 15px;
  background: var(--bg2); color: var(--t1);
  border: 1px solid var(--line2); border-radius: var(--r-s, 10px);
  padding: 4px 10px; max-width: 260px; cursor: pointer;
}
.proj-select:disabled { opacity: 0.6; cursor: wait; }
.proj-add {
  font: inherit; font-size: 12px; font-weight: 700;
  background: var(--accent-dim); color: var(--t1);
  border: 1px solid var(--line2); border-radius: 999px;
  padding: 4px 12px; cursor: pointer;
}
.proj-add:hover { border-color: var(--accent); }
.proj-add:disabled { opacity: 0.5; cursor: wait; }
.proj-meta { background: var(--bg2); color: var(--t2); }
.sys { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.meter { display: flex; align-items: center; gap: 8px; }
.bar {
  width: 76px; height: 5px; border-radius: 3px;
  background: var(--bg3); overflow: hidden;
}
.bar i { display: block; height: 100%; background: linear-gradient(90deg, var(--teal), var(--accent)); }
.meter-num { font-size: 11px; color: var(--t2); }
.status-chip { background: var(--bg2); color: var(--t2); }
.mode-live { background: rgba(52, 214, 198, 0.12); color: var(--teal); letter-spacing: 0.08em; }
.mode-demo { background: rgba(245, 185, 63, 0.12); color: var(--amber, #f5b93f); }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot.ok { background: var(--green); box-shadow: 0 0 6px var(--green); }
.avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--bg3); border: 1px solid var(--line2);
  display: grid; place-items: center;
  font-size: 10px; font-weight: 700; color: var(--t2);
}
.rail {
  grid-area: rail;
  background: var(--bg1);
  border-right: 1px solid var(--line);
  padding: 14px 10px;
  display: flex; flex-direction: column;
}
.step {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 12px; border-radius: var(--r-s);
  color: var(--t2); text-decoration: none;
  margin-bottom: 2px; position: relative;
  transition: all 0.15s;
}
.step:hover { background: var(--bg2); color: var(--t1); }
.step.on { background: var(--accent-dim); color: #fff; }
.step.on::before {
  content: ''; position: absolute; left: 0; top: 20%; bottom: 20%;
  width: 3px; border-radius: 2px; background: var(--accent);
}
.step-no { font-family: var(--mono); font-size: 11px; color: var(--t3); }
.step.on .step-no { color: var(--accent); }
.step-name { font-size: 13.5px; font-weight: 600; }
.step-tag {
  margin-left: auto; font-size: 10.5px; font-family: var(--mono);
  background: var(--bg3); padding: 1px 7px; border-radius: 999px; color: var(--t2);
}
.main { grid-area: main; overflow: auto; padding: 22px 26px 26px; }
.toasts { position: fixed; right: 18px; bottom: 86px; display: flex; flex-direction: column; gap: 8px; z-index: 50; }
.toast {
  max-width: 360px; padding: 9px 14px; border-radius: var(--r-s, 10px);
  background: var(--bg2); border: 1px solid var(--line2, #2a3140); color: var(--t1);
  font-size: 12.5px; box-shadow: 0 8px 24px rgba(0,0,0,.5);
  animation: toast-in .18s ease-out;
}
.toast.k-ok { border-color: rgba(52,214,198,.4); }
.toast.k-warn { border-color: rgba(245,185,63,.45); }
.toast.k-err { border-color: rgba(255,107,107,.5); }
@keyframes toast-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; } }
.toast-move { transition: transform 0.4s ease; }
.toast-leave-active { transition: opacity 0.9s ease, transform 0.9s ease; position: absolute; }
.toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
