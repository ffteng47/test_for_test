// 单例 HTML5 播放器：TransportBar / 试听 / 成品回放共用。
// 状态写回 store.transport，组件只读，不各自 new Audio()。
import { store, toast } from '../data/store.js'

const audio = new Audio()
audio.preload = 'metadata'
audio.addEventListener('play', () => { store.transport.playing = true })
audio.addEventListener('pause', () => { store.transport.playing = false })
audio.addEventListener('ended', () => { store.transport.playing = false })
audio.addEventListener('error', () => {
  if (audio.src) toast(`音频加载失败：${audio.src.split('/').pop()}`, 'err')
})
audio.addEventListener('timeupdate', () => {
  store.transport.elapsed = Math.round(audio.currentTime * 1000)
  if (audio.duration && isFinite(audio.duration)) store.transport.duration = Math.round(audio.duration * 1000)
})

export function playUrl(url, segId = 0) {
  if (!url) return
  if (audio.src !== location.origin + url) {
    audio.src = url
    audio.currentTime = 0
    store.transport.elapsed = 0
    store.transport.duration = 0
    store.transport.url = url
    store.transport.segId = segId
  }
  audio.play().catch((e) => {
    store.transport.playing = false
    toast(`播放失败：${e && e.name ? e.name : e}`, 'err')
  })
}

export function toggleUrl(url, segId = 0) {
  const same = audio.src === location.origin + url
  if (same) {
    if (store.transport.playing) { audio.pause(); return }
    if (audio.ended || audio.currentTime >= (audio.duration || 0)) audio.currentTime = 0
    audio.play().catch((e) => toast(`播放失败：${e && e.name ? e.name : e}`, 'err'))
    return
  }
  playUrl(url, segId)
}

export function stop() {
  audio.pause()
  audio.currentTime = 0
  store.transport.playing = false
  store.transport.elapsed = 0
}
