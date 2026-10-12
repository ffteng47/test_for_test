<template>
  <div>
    <div class="view-head">
      <div>
        <div class="view-title">母带导出</div>
        <div class="view-sub">FFmpeg ffmetadata 章节时间轴 · 按音频实际时长计算起止 · M4B 带章节跳转</div>
      </div>
      <div class="head-actions">
        <button class="btn btn-primary" @click="startExport">＋ 新建导出</button>
      </div>
    </div>

    <div class="grid2">
      <!-- 导出配置 -->
      <div class="card panel">
        <div class="panel-head"><span class="label">NEW EXPORT · 导出配置</span></div>
        <div class="cfg">
          <div class="field">
            <div class="label">格式</div>
            <div class="fmt-row">
              <button
                v-for="f in formats"
                :key="f.key"
                class="fmt-btn"
                :class="{ on: fmt === f.key }"
                @click="fmt = f.key"
              >
                <b>{{ f.key }}</b>
                <span>{{ f.desc }}</span>
              </button>
            </div>
          </div>
          <div class="field">
            <div class="label">收录章节</div>
            <div class="ch-pick">
              <label v-for="ch in store.chapters" :key="ch.id" class="pick" :class="{ off: ch.status !== 'generated' }">
                <input type="checkbox" :disabled="ch.status !== 'generated'" v-model="picked" :value="ch.id" />
                <span>{{ ch.title }}</span>
              </label>
            </div>
            <div class="hint dim">仅「音频已生成」的章节可收录；未确认锁定的段落会按当前选用版本导出。</div>
          </div>
          <div class="field two">
            <div>
              <div class="label">比特率</div>
              <select v-model="bitrate">
                <option>64k</option><option>96k</option><option selected>128k</option><option>192k</option>
              </select>
            </div>
            <div>
              <div class="label">封面</div>
              <select v-model="cover">
                <option>自动生成（书名+作者）</option>
                <option>不嵌入</option>
              </select>
            </div>
          </div>
          <div class="field">
            <div class="label">元数据</div>
            <div class="meta-grid mono">
              <span title="TITLE">书名 {{ store.project.title }}</span>
              <span title="AUTHOR">作者 {{ store.project.author }}</span>
              <span title="NARRATOR">演播 AI · Qwen3-TTS</span>
              <span title="LANGUAGE">语言 zh-CN</span>
            </div>
          </div>
          <div v-if="runJob" class="exp-run">
            <div class="run-head">
              <span class="spin"></span>
              <b>{{ runJob.name }}</b>
              <span class="dim">进行中——完成后自动刷新产物列表</span>
            </div>
            <div class="run-bar"><i></i></div>
            <div class="run-log mono dim">{{ (runJob.logs || []).slice(-1)[0] || '等待后端输出…' }}</div>
          </div>

          <div class="field">
            <div class="label">导出前检查 · pre-flight</div>
            <div class="validator card2">
              <template v-if="store.system.continuity || store.system.qc">
                <div class="vrow" v-if="store.system.continuity"><span :class="store.system.continuity.sim >= 0.999 ? 't-ok' : 't-warn'">
                  {{ store.system.continuity.sim >= 0.999 ? '✓' : '!' }}</span>
                  <span>原文字级一致率 {{ (store.system.continuity.sim * 100).toFixed(1) }}%（漏 {{ store.system.continuity.missing }} · 增 {{ store.system.continuity.added }}）</span></div>
                <div class="vrow" v-if="store.system.qc"><span :class="store.system.qc.retry ? 't-warn' : 't-ok'">{{ store.system.qc.retry ? '!' : '✓' }}</span>
                  <span>音频回听质检：{{ store.system.qc.pass }} 通过 · {{ store.system.qc.retry }} 待复核 · {{ store.system.qc.unchecked }} 未检</span></div>
                <div class="vrow"><span :class="pendingSegs ? 't-warn' : 't-ok'">{{ pendingSegs ? '!' : '✓' }}</span>
                  <span>{{ pendingSegs ? pendingSegs + ' 段尚无音频，导出将跳过' : '全部段落已有音频' }}</span></div>
                <div class="vrow"><span :class="retrySegs ? 't-warn' : 't-ok'">{{ retrySegs ? '!' : '✓' }}</span>
                  <span>{{ retrySegs ? retrySegs + ' 段质检待复核（原文差异或音频不符），建议先处理' : '无待复核差异段' }}</span></div>
                <div class="vrow" v-if="listen"><span :class="listen.未审段数 ? 't-warn' : 't-ok'">{{ listen.未审段数 ? '!' : '✓' }}</span>
                  <span>人工审听 {{ listen.已审段数 }}/{{ listen.总段数 }} 段 · 未审 {{ listen.未审段数 }}
                    · 错读 {{ listen.计数.misread }} / 音色 {{ listen.计数.timbre }} / 需重生成 {{ listen.计数.regen }}
                    · 工时 {{ Math.round(listen.人工工时s / 60) }} min<span v-if="listen.未审段数">（机检听不出音色漂移和合法异读，这一遍没跑完就别按合格交付）</span></span></div>
              </template>
              <template v-else>
                <div class="vrow"><span class="dim i">–</span><span>未连接质检数据（连续性/ASR 回听），导出仍可进行</span></div>
              </template>
            </div>
          </div>
          <button class="btn btn-primary full" :disabled="exporting" @click="startExport">
            {{ exporting ? '导出中…（看任务队列）' : `开始导出 ${fmt}` }}
          </button>
        </div>
      </div>

      <!-- 导出历史 -->
      <div class="card panel">
        <div class="panel-head">
          <span class="label">LIBRARY · 导出产物</span>
          <span class="chip chip-dim">{{ store.exports.length }}</span>
        </div>

        <!-- 机检闸门：读 projects/<slug>/delivery_report.json 的「通过」，不合格禁下载 -->
        <div class="gate" :class="gateClass">
          <template v-if="delivery">
            <div class="gate-head">
              <b :class="{ 't-err': delivery.通过 === false }">{{ delivery.通过 === false ? '✕ 机检不通过 · 禁止交付' : '✓ 机检通过' }}</b>
              <span class="dim mono">{{ delivery.书 || '当前书' }} · {{ (delivery.输出 || '').split('/').pop() }}</span>
            </div>
            <div class="gate-nums mono" v-if="delivery.全项实测">
              {{ delivery.全项实测.LUFS }} LUFS · {{ delivery.全项实测.真峰值dBTP }} dBTP
              · {{ delivery.全项实测.章节数 }} 章 · {{ delivery.章节数 }}
            </div>
            <div class="vrow" v-for="(ok, k) in (delivery.验收 || {})" :key="k">
              <span :class="ok ? 't-ok' : 't-err'">{{ ok ? '✓' : '✕' }}</span><span>{{ k }}</span>
            </div>
          </template>
          <div v-else class="vrow"><span class="dim i">–</span><span>未机检：这本书还没走过母带后期，成品按不合格对待</span></div>
        </div>

        <div v-for="e in store.exports" :key="e.id" class="exp-row" :class="{ bad: e.blocked }">
          <div class="exp-icon" :class="'fi-' + e.format.toLowerCase()">
            {{ e.format }}
          </div>
          <div class="exp-main">
            <div class="exp-name">{{ e.name }}</div>
            <div class="exp-sub mono">{{ e.size }} · {{ e.chapters }} 章 · {{ e.time }}</div>
          </div>
          <div class="exp-acts">
            <button class="btn btn-ghost btn-xs" @click="play(e)">{{ isPlaying(e) ? '■ 停止' : '播放' }}</button>
            <button class="btn btn-ghost btn-xs" :disabled="e.blocked"
                    :title="e.blocked ? '机检不通过，先重新导出' : ''" @click="download(e)">下载</button>
            <button class="btn btn-ghost btn-xs" @click="del(e)">删除</button>
          </div>
        </div>

        <div class="panel-foot dim">
          产物落 <span class="mono">alexandria/</span>（按当前书归档），导出记录可在任务队列回看。
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { store, toast } from '../data/store.js'
import { actions } from '../api/actions.js'
import { toggleUrl } from '../audio/player.js'

export default {
  name: 'ExportView',
  data() {
    return {
      store,
      fmt: 'M4B',
      bitrate: '128k',
      cover: '自动生成（书名+作者）',
      picked: [1],
      formats: [
        { key: 'M4B', desc: '章节跳转 · 有声书 App' },
        { key: 'MP3', desc: '单文件 · 兼容最广' },
        { key: 'WAV', desc: '无损 · 后期母带' }
      ]
    }
  },
  computed: {
    busy() { return this.store.busy },
    exporting() { return !!(this.store.busy.audio || this.store.busy.m4b_export) },
    runJob() {
      return this.store.jobs.find((j) => j.status === 'running' &&
        (j.task === 'audio' || j.task === 'm4b_export')) || null
    },
    pendingSegs() { return this.store.segments.filter(s => s.status !== 'done').length },
    retrySegs() { return this.store.segments.filter(s => s.qc === 'retry').length },
    delivery() { return this.store.system.delivery },
    listen() { return this.store.system.listen },
    gateClass() {
      if (!this.delivery) return 'gate-none'
      return this.delivery.通过 === false ? 'gate-bad' : 'gate-ok'
    }
  },
  methods: {
    startExport() {
      if (this.fmt === 'MP3') actions.mergeMp3()
      else if (this.fmt === 'M4B') actions.mergeM4b({
        perChunkChapters: true,
        title: this.store.project.title,
        author: this.store.project.author,
        narrator: '旁白',
        year: String(new Date().getFullYear()),
        description: ''
      })
      else toast('WAV 母带导出在后端阶段 4 接通', 'warn')
    },
    download(e) {
      window.open(e.url || '/api/audiobook', '_blank')
    },
    // 单例播放器：整书动辄 25 分钟，播着必须能停，所以按钮跟着状态变成「停止」
    isPlaying(e) {
      return this.store.transport.playing && this.store.transport.url === (e.url || '/api/audiobook')
    },
    play(e) {
      toggleUrl(e.url || '/api/audiobook', 0)
    },
    del(e) {
      store.exports = store.exports.filter(x => x.id !== e.id)
    }
  }
}
</script>

<style scoped>
.grid2 { display: grid; grid-template-columns: 1fr 1.1fr; gap: 16px; align-items: start; }
.panel { overflow: hidden; }
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--line);
}
.panel-foot { padding: 12px 16px; font-size: 11.5px; border-top: 1px dashed var(--line); }
.chip-dim { background: var(--bg3); color: var(--t2); }

.cfg { padding: 16px; }
.field { margin-bottom: 16px; }
.fmt-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
.fmt-btn {
  background: var(--bg2); border: 1px solid var(--line2); border-radius: var(--r-s);
  padding: 10px 8px; cursor: pointer; text-align: left; color: var(--t2);
  display: flex; flex-direction: column; gap: 2px; transition: all 0.15s;
}
.fmt-btn b { color: var(--t1); font-size: 13px; }
.fmt-btn span { font-size: 11px; }
.fmt-btn:hover { border-color: var(--accent); }
.fmt-btn.on { border-color: var(--accent); background: var(--accent-dim); }
.fmt-btn.on b { color: var(--accent); }

.ch-pick { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.pick {
  display: flex; align-items: center; gap: 8px; font-size: 13px;
  padding: 6px 10px; border-radius: var(--r-s); cursor: pointer;
}
.pick:hover { background: var(--bg2); }
.pick.off { opacity: 0.4; cursor: not-allowed; }
.pick input[type='checkbox'] { width: 14px; height: 14px; accent-color: var(--accent); }
.hint { font-size: 11.5px; margin-top: 8px; }

.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.meta-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px;
  margin-top: 8px; font-size: 12px; color: var(--t2);
  background: var(--bg0); border: 1px solid var(--line);
  border-radius: var(--r-s); padding: 10px 12px;
}
.full { width: 100%; justify-content: center; padding: 10px; }

.exp-row {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 16px; border-bottom: 1px solid var(--line);
}
.exp-row.bad .exp-name { color: var(--red); }

.gate { padding: 11px 16px; border-bottom: 1px solid var(--line); font-size: 12.5px; }
.gate-none { color: var(--t2); }
.gate-bad { background: rgba(240, 102, 95, 0.08); }
.gate-head { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
.gate-nums { font-size: 11.5px; color: var(--t2); margin-bottom: 2px; }
.exp-icon {
  flex: none; width: 50px; text-align: center;
  font-size: 11px; font-weight: 800; padding: 8px 0;
  border-radius: var(--r-s);
}
.fi-m4b { background: var(--accent-dim); color: var(--accent); }
.fi-mp3 { background: rgba(52, 214, 198, 0.12); color: var(--teal); }
.fi-wav { background: rgba(245, 185, 63, 0.12); color: var(--amber); }
.exp-main { flex: 1; min-width: 0; }
.exp-name { font-weight: 600; font-size: 13px; }
.exp-sub { font-size: 11.5px; color: var(--t2); margin-top: 2px; }
.exp-acts { display: flex; gap: 6px; }
.btn-xs { padding: 3px 10px; font-size: 12px; }

.validator { padding: 10px 12px; background: var(--bg2); border: 1px solid var(--line); border-radius: var(--r-s); }
.vrow {
  display: flex; gap: 10px; align-items: baseline;
  font-size: 12.5px; color: var(--t2); padding: 5px 0;
}
.vrow .t-ok, .vrow .t-warn, .vrow .t-err { font-weight: 700; }
.vrow .i { font-weight: 700; }

.exp-run {
  margin: 2px 0 16px; padding: 12px 14px;
  border: 1px solid rgba(124, 108, 255, 0.4); border-radius: var(--r-s);
  background: var(--accent-dim);
}
.run-head { display: flex; align-items: center; gap: 10px; font-size: 13px; margin-bottom: 10px; }
.run-log { font-size: 11px; margin-top: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.run-bar { height: 6px; border-radius: 3px; background: var(--bg3); overflow: hidden; position: relative; }
.run-bar i {
  position: absolute; inset: 0; width: 40%; border-radius: 3px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--teal), transparent);
  animation: run-slide 1.2s linear infinite;
}
@keyframes run-slide { from { transform: translateX(-110%); } to { transform: translateX(260%); } }
.spin {
  width: 12px; height: 12px; flex: none; border-radius: 50%;
  border: 2px solid var(--accent); border-top-color: transparent;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
