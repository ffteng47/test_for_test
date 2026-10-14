// 批量生成任务的进度换算：HUD、CastView、StudioView 共用，避免三处各写一份漂移。
// 数据来源是 actions.track() 解析后端 `Progress: X/Y (D done, F failed)` 后写进 job 的 done/total/failed。

// 从后端日志取最后一条 `Progress: 179/273 (179 done, 0 failed)`；无匹配返回 null。
export function parseProgress(logs) {
  for (let i = logs.length - 1; i >= 0; i--) {
    const m = /Progress:\s*(\d+)\/(\d+)\s*\((\d+)\s+done,\s*(\d+)\s+failed\)/.exec(logs[i])
    if (m) return { done: +m[1], total: +m[2], failed: +m[4] }
  }
  return null
}

// 把一条日志数组解析出的进度写回 job，并顺手算 progress%。
// finished 为真时（任务已结束）允许显示到 100%，否则封顶 99 防「没完就先 100」。
export function applyProgress(job, logs, finished) {
  const p = parseProgress(logs)
  if (!p) return
  job.done = p.done; job.total = p.total; job.failed = p.failed
  job.progress = p.total
    ? (finished ? 100 : Math.min(99, Math.round((p.done + p.failed) / p.total * 100)))
    : 50
}

export function pct(j) {
  return j.total ? Math.min(100, Math.round(j.done / j.total * 100)) : 0
}

export function remain(j) {
  return Math.max(0, j.total - j.done - j.failed)
}

// 秒数 → `Xs` / `XmYYs` / `XhYYm`
export function fmtDur(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`
}

export function elapsed(j, now) {
  return fmtDur((now - (j.startedAt || now)) / 1000)
}

// 按当前平均产速估剩余；样本太少（<2 段）或刚起步时返回 ''，不谎报 ETA
export function eta(j, now) {
  const finished = j.done + j.failed
  if (!j.total || finished < 2) return ''
  const secs = (now - (j.startedAt || now)) / 1000
  if (secs < 1) return ''
  return fmtDur((remain(j) / finished) * secs)
}
