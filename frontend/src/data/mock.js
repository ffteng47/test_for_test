// 模拟数据层：形状与 target-architecture.md §2 的 DB 契约一致，联调时替换为真实 API
const SPEAKERS = {
  narrator: { name: '旁白', color: '#8fa3bf' },
  chenmo:   { name: '陈默', color: '#7c6cff' },
  linwan:   { name: '林晚', color: '#e06fa8' },
  oldzhou:  { name: '老周', color: '#f5b93f' },
  xiaoman:  { name: '小满', color: '#34d6c6' }
}

const RAW_SEGMENTS = [
  ['narrator', '雨下到第三天的时候，青石巷的积水已经漫过了门槛。陈默站在屋檐下，望着巷口，像在等一个不会来的人。', '平静、克制的叙述，语速稍缓，带一点潮湿的阴郁'],
  ['linwan', '「你怎么还不走？」', '年轻女声，微嗔，尾音上扬，雨声背景下的急促'],
  ['narrator', '林晚撑伞站在台阶上，裙脚已经湿了半寸。她手里还捏着那封没写完的信，边角被雨泡软了。', '叙述中带细节描摹，语气轻柔'],
  ['chenmo', '「等雨停。」陈默没有回头，「你回去罢，让人看见不好看。」', '低沉男声，疲惫而隐忍，句间有短暂停顿'],
  ['linwan', '「不好看的事，我们做得还少吗？」', '压着声音的质问，微颤，克制的眼眶发热的感觉'],
  ['narrator', '巷子里安静下来，只有雨打在伞骨上的声音。很久，陈默从怀里摸出一样东西，托在掌心。', '留白式叙述，节奏放慢，制造悬念'],
  ['chenmo', '「这个，你替我收着。等……等一个合适的时机。」', '犹豫，声音渐低，"合适的时机"四字略微加重'],
  ['narrator', '那是一枚磨得发亮的铜哨，是三年前在山道上捡的，当时谁也没有想到，它会成一句暗号。', '回忆性叙述，语气微暖，带命运感的从容'],
  ['oldzhou', '「少爷！少爷，老爷请您回去——」', '苍老的男声，急切但恭敬，隔着雨声喊话'],
  ['narrator', '老周撑着歪斜的伞小跑过来，目光在陈默与林晚之间来回打了个转，把后半句话咽了回去。', '第三人称全知视角，观察细致，略带幽默的收敛'],
  ['linwan', '「你走吧。」林晚忽然笑了一下，把伞举高了些，「别淋坏了，铜哨要干了才吹得响。」', '释然的轻笑，坚强里藏着不舍，尾句轻快'],
  ['narrator', '陈默终于回过头。雨幕里，她的伞像一朵开倒了的白花。他想起很多年后，自己仍会记得这一幕，记得这个潮湿的、没有告别成的早晨。', '时间跨度拉长的收束叙述，深沉怅惘，末句渐弱']
]

export const store = {
  system: { gpuUsed: 14.2, gpuTotal: 24, freeGb: 341, ollama: 'qwen3:8b', ready: true, continuity: null, qc: null, delivery: null, listen: null },

  project: { title: '《青石巷》', author: '佚名', lang: 'zh', totalChapters: 12 },

  chapters: [
    { id: 1, title: '第一章 雨季', status: 'generated', duration: 420000 },
    { id: 2, title: '第二章 铜哨', status: 'annotated', duration: 0 },
    { id: 3, title: '第三章 山道', status: 'annotated', duration: 0 },
    { id: 4, title: '第四章 旧信', status: 'pending', duration: 0 },
    { id: 5, title: '第五章 归途', status: 'pending', duration: 0 }
  ],

  segments: RAW_SEGMENTS.map(([speaker, text, instruct], i) => ({
    id: i + 1,
    order: i + 1,
    speaker,
    kind: speaker === 'narrator' ? 'narration' : 'dialogue',
    text,
    instruct,
    duration: Math.round((text.length / 4.5)) * 1000,
    status: i < 9 ? 'done' : i === 9 ? 'error' : 'pending',
    qc: i < 7 ? 'pass' : i === 9 ? 'retry' : null,
    versions: i < 9 ? 2 : 1,
    chosen: i + 1,
    listen: null
  })),

  characters: [
    { id: 'chenmo', name: '陈默', aliases: ['少爷', '默哥', '陈公子'], lines: 86, desc: '二十四岁，长房嫡子，隐忍克制', voiceId: 'v-chenmo-2' },
    { id: 'linwan', name: '林晚', aliases: ['晚晚', '林家妹妹'], lines: 64, desc: '二十岁，书铺之女，外柔内刚', voiceId: 'v-linwan-1' },
    { id: 'oldzhou', name: '老周', aliases: ['周伯', '少爷的家人'], lines: 18, desc: '五十六岁，陈家老仆', voiceId: null },
    { id: 'xiaoman', name: '小满', aliases: ['满儿'], lines: 9, desc: '十二岁，林晚的弟弟', voiceId: null },
    { id: 'narrator', name: '旁白', aliases: [], lines: 210, desc: '全书叙述声', voiceId: 'v-narrator-3' }
  ],

  voices: [
    { id: 'v-narrator-3', name: '沉稳叙述·男', mode: 'design', model: 'VoiceDesign', locked: true, dur: '8.2s' },
    { id: 'v-chenmo-2', name: '陈默·清隐', mode: 'clone', model: 'Base', locked: true, dur: '12.4s' },
    { id: 'v-chenmo-1', name: '陈默·旧版', mode: 'clone', model: 'Base', locked: false, dur: '11.0s' },
    { id: 'v-linwan-1', name: '林晚·雨柔', mode: 'clone', model: 'Base', locked: false, dur: '10.6s' },
    { id: 'v-custom-serena', name: 'Serena（内置）', mode: 'custom', model: 'CustomVoice', locked: false, dur: '—' },
    { id: 'v-custom-ryan', name: 'Ryan（内置）', mode: 'custom', model: 'CustomVoice', locked: false, dur: '—' }
  ],

  jobs: [
    { id: 42, name: '第二章 TTS 批量生成', type: 'tts', progress: 67, eta: '04:12', status: 'running' },
    { id: 41, name: '第三章 剧本标注', type: 'annotate', progress: 100, eta: '', status: 'done' },
    { id: 40, name: '第二章 ASR 质检', type: 'qc', progress: 100, eta: '', status: 'warn' }
  ],

  exports: [
    { id: 1, name: '《青石巷》全一册.m4b', format: 'M4B', size: '86.4 MB', chapters: 5, time: '今天 09:12' },
    { id: 2, name: '第一章 雨季.mp3', format: 'MP3', size: '9.2 MB', chapters: 1, time: '昨天 22:40' }
  ],

  transport: { playing: false, url: '', segId: 0, elapsed: 0, duration: 0 },

  speakers: SPEAKERS
}

export function speakerOf(id) {
  return SPEAKERS[id] || { name: id, color: '#666' }
}

export function fmtTime(ms) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
