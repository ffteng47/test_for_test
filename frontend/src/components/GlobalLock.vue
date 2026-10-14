<template>
  <transition name="glock">
    <div v-if="store.lock.on" class="glock">
      <div class="glock-card">
        <div class="glock-spin"></div>
        <div class="glock-text">{{ store.lock.text }}</div>
        <div class="glock-sub">操作已锁定，请稍候…</div>
      </div>
    </div>
  </transition>
</template>

<script>
import { store } from '../data/store.js'

export default {
  name: 'GlobalLock',
  data: () => ({ store })
}
</script>

<style scoped>
.glock {
  position: fixed; inset: 0; z-index: 70;
  display: grid; place-items: center;
  background: rgba(8, 11, 18, 0.66); backdrop-filter: blur(3px);
  cursor: progress; user-select: none;
}
.glock-card {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  padding: 28px 40px; border-radius: 16px;
  background: var(--bg1); border: 1px solid var(--accent-dim, rgba(124,108,255,.4));
  box-shadow: 0 20px 60px rgba(0,0,0,.55), 0 0 0 1px rgba(124,108,255,.12);
}
.glock-spin {
  width: 38px; height: 38px; border-radius: 50%;
  border: 3px solid var(--line2); border-top-color: var(--accent);
  animation: glock-rot 0.8s linear infinite;
}
@keyframes glock-rot { to { transform: rotate(360deg); } }
.glock-text { font-size: 14px; font-weight: 700; color: var(--t1); }
.glock-sub { font-size: 11.5px; color: var(--t3); margin-top: -8px; }
.glock-enter-active, .glock-leave-active { transition: opacity 0.18s ease; }
.glock-enter-from, .glock-leave-to { opacity: 0; }
</style>
