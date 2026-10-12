// 自检：`store.X = ...` 赋值的顶层键，必须在进 reactive() 的那个对象里就已经存在。
// reactive() 之后才挂的键不被追踪，读它的 computed 会永远缓存初值
// （TransportBar 的 live() 卡成 false、播放按钮点了没反应就是这么死的）。
// 跑法：node frontend/check-store-shape.mjs
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { store as mockStore } from './src/data/mock.js'

const dir = path.dirname(fileURLToPath(import.meta.url))
const src = fs.readFileSync(path.join(dir, 'src/data/store.js'), 'utf8')

const reactiveBlock = (src.match(/export const store = reactive\(([\s\S]*?)\)\n\n/) || ['', ''])[1]
const seeded = new Set([...reactiveBlock.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/gm)].map((m) => m[1]))
// reactive(...) 里引用的基础形状（structuredClone(mockStore)）也算已存在
const base = new Set(Object.keys(mockStore))
const known = new Set([...seeded, ...base])

const assigned = [...src.matchAll(/^store\.([A-Za-z_][A-Za-z0-9_]*)\s*=[^=]/gm)].map((m) => m[1])
const late = [...new Set(assigned.filter((k) => !known.has(k)))]

// loader 事后挂到段/system 上的字段同理：段字面量与 system 初值必须都声明出来
const segLiteral = (src.match(/store\.segments = chunks\.map[\s\S]*?return \{([\s\S]*?)\n    \}/) || ['', ''])[1]
const segKeys = new Set([...segLiteral.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/gm)].map((m) => m[1]))
const segLate = ['listen', 'qc', 'qcErr'].filter((k) => !segKeys.has(k))
const sysKeys = new Set(Object.keys(mockStore.system))
const sysLate = ['qc', 'delivery', 'listen'].filter((k) => !sysKeys.has(k))

if (late.length || segLate.length || sysLate.length) {
  console.error('FAIL 事后挂键（computed 会读不到变化）:', { late, segLate, sysLate })
  process.exit(1)
}
console.log('OK store 形状完整:', { known: known.size, segments: [...segKeys].length, system: [...sysKeys].length })
