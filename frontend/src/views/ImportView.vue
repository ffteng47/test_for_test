<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">导入拆解</div>
        <div class="view-sub">EPUB / TXT / DOCX → 章节识别 → 段落定位入库（可回链原文）</div>
      </div>
      <div class="head-actions">
        <input ref="file" type="file" accept=".txt,.epub" style="display:none" @change="onFile">
        <button class="btn" :disabled="busy.script" @click="actions.generateScript()">{{ busy.script ? '标注中…' : '⟳ 标注剧本' }}</button>
        <button class="btn" :disabled="busy.review" @click="actions.reviewScript()">{{ busy.review ? '复查中…' : '✓ 复查' }}</button>
        <button class="btn btn-primary" :disabled="uploading" @click="$refs.file.click()">{{ uploading ? '上传中…' : '+ 上传书稿' }}</button>
      </div>
    </div>

    <div class="drop card" @click="$refs.file.click()">
      <div class="drop-icon">⇪</div>
      <div class="drop-text">拖入 <b>.txt</b> 文件，或点击选择（走后端 /api/upload）<br>
        <span class="dim" style="font-size:12px">EPUB/DOCX 支持在路线图阶段 4.1（E2A 解析链）</span></div>
      <div v-if="store.system.continuity" class="cont mono">
        原文一致率 {{ (store.system.continuity.sim * 100).toFixed(1) }}% · 漏字 {{ store.system.continuity.missing }} · 增字 {{ store.system.continuity.added }}
      </div>
    </div>

    <div class="split">
      <div class="card list">
        <div class="label list-head">章节树 · 第一章至第五章</div>
        <div v-for="c in store.chapters" :key="c.id" class="ch">
          <span class="mono ch-no">{{ String(c.id).padStart(2, '0') }}</span>
          <span class="ch-name">{{ c.title }}</span>
          <span class="chip st" :class="'st-' + c.status">
            {{ { generated: '已生成', annotated: '已标注', pending: '待处理' }[c.status] }}
          </span>
        </div>
      </div>
      <div class="card preview">
        <div class="label list-head">正文预览 · 段落定位映射</div>
        <div class="pv-line" v-for="(s, i) in store.segments.slice(0, 6)" :key="i">
          <span class="mono pv-loc">L{{ 12 + i * 7 }}:{{ 3 + i }}</span>
          <span>{{ s.text }}</span>
        </div>
        <div class="dim note">每段保留 raw/clean 双文本与字符偏移，生成音频后可反向定位原文。</div>
      </div>
    </div>
  </div>
</template>

<script>
import { store } from '../data/store.js'
import { actions } from '../api/actions.js'
export default {
  data: () => ({ store, actions, uploading: false }),
  computed: {
    busy() { return this.store.busy }
  },
  methods: {
    async onFile(e) {
      const f = e.target.files[0]
      if (!f) return
      this.uploading = true
      const ok = await actions.uploadBook(f)
      this.uploading = false
      if (ok) actions.generateScript()
      e.target.value = ''
    }
  }
}
</script>

<style scoped>
.drop {
  border-style: dashed; border-width: 2px; padding: 34px;
  text-align: center; margin-bottom: 18px; cursor: pointer;
  background: linear-gradient(180deg, var(--bg1), var(--bg0));
}
.drop:hover { border-color: var(--accent); }
.cont { margin-top: 10px; font-size: 11.5px; color: var(--teal); }
.drop-icon { font-size: 26px; color: var(--accent); margin-bottom: 8px; }
.drop-text { color: var(--t2); font-size: 13.5px; line-height: 1.8; }
.split { display: grid; grid-template-columns: 5fr 6fr; gap: 18px; }
.list, .preview { padding: 14px 16px; }
.list-head { padding: 4px 0 10px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.ch { display: flex; align-items: center; gap: 12px; padding: 9px 6px; border-radius: 8px; }
.ch:hover { background: var(--bg2); }
.ch-no { color: var(--t3); font-size: 12px; }
.ch-name { flex: 1; font-size: 13.5px; }
.st { font-size: 11px; }
.st-generated { background: rgba(74, 222, 128, 0.13); color: var(--green); }
.st-annotated { background: var(--accent-dim); color: var(--accent); }
.st-pending { background: var(--bg3); color: var(--t3); }
.pv-line {
  font-size: 12.5px; color: var(--t2); padding: 7px 0;
  border-bottom: 1px dashed var(--line); display: flex; gap: 10px;
}
.pv-loc { color: var(--teal); font-size: 11px; flex: none; padding-top: 2px; }
.note { font-size: 12px; margin-top: 12px; }
</style>
