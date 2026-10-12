<template>
  <div class="tag-editor">
    <label v-for="f in facets" :key="f.key" class="te-field">
      <span class="te-label">{{ f.label }}<i v-if="f.measured" class="te-m" title="入库时由音频实测，可手工覆盖">实测</i></span>

      <select v-if="f.kind === 'enum' && !f.multi" :value="pick(f.key)" @change="write(f.key, $event.target.value)">
        <option value="">未标</option>
        <option v-for="v in f.values" :key="v" :value="v">{{ labelOf(f, v) }}</option>
      </select>

      <span v-else-if="f.kind === 'enum'" class="te-chips">
        <button type="button" v-for="v in f.values" :key="v" class="te-chip" :class="{ on: has(f.key, v) }"
                @click="toggle(f.key, v)">{{ labelOf(f, v) }}</button>
      </span>

      <span v-else-if="f.kind === 'num'" class="te-range">
        <input type="range" :min="f.min" :max="f.max" :step="f.step" :value="pick(f.key)" @input="write(f.key, Number($event.target.value))" />
        <b>{{ shown(f) }}</b>
        <button type="button" class="te-reset" @click="write(f.key, '')">清</button>
      </span>

      <input v-else-if="f.kind === 'int'" type="number" :min="f.min" :max="f.max" :value="pick(f.key)"
             @change="write(f.key, $event.target.value)" />

      <input v-else type="text" :maxlength="f.max_len" :value="pick(f.key)" :placeholder="f.label"
             @change="write(f.key, $event.target.value)" />
    </label>
  </div>
</template>

<script>
// 维度全部来自 /api/vault/schema（后端 tag_vocab.py 是唯一真源）：加一维只改后端，这里不用动。
export default {
  name: 'TagEditor',
  props: { facets: { type: Array, default: () => [] }, value: { type: Object, default: () => ({}) } },
  methods: {
    pick(key) {
      const v = (this.value || {})[key]
      return v === undefined || v === null ? '' : v
    },
    labelOf(facet, val) {
      return (facet.value_labels && facet.value_labels[val]) || val
    },
    shown(facet) {
      const v = (this.value || {})[facet.key]
      return v === undefined || v === null || v === '' ? '—' : Number(v).toFixed(2)
    },
    has(key, val) {
      const cur = (this.value || {})[key]
      return Array.isArray(cur) && cur.indexOf(val) >= 0
    },
    toggle(key, val) {
      const cur = ((this.value || {})[key] || []).slice()
      const i = cur.indexOf(val)
      if (i >= 0) cur.splice(i, 1)
      else cur.push(val)
      this.write(key, cur)
    },
    write(key, val) {
      const next = Object.assign({}, this.value)
      if (val === '' || val === null || (Array.isArray(val) && !val.length)) delete next[key]
      else next[key] = val
      this.$emit('input', next)
    }
  }
}
</script>

<style scoped>
.tag-editor { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px 14px; }
.te-field { display: flex; flex-direction: column; gap: 4px; }
.te-label { font-size: 11px; color: var(--t2); letter-spacing: .04em; }
.te-m { font-style: normal; margin-left: 4px; color: var(--accent); font-size: 10px; }
.te-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.te-chip { font-size: 11px; padding: 2px 7px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--t2); cursor: pointer; }
.te-chip.on { border-color: var(--accent); color: var(--accent); background: rgba(124, 108, 255, .12); }
.te-range { display: flex; align-items: center; gap: 8px; }
.te-range input { flex: 1; }
.te-range b { font-size: 12px; min-width: 34px; text-align: right; }
.te-reset { font-size: 11px; padding: 1px 6px; border: 1px solid var(--line); background: transparent; color: var(--t2); cursor: pointer; border-radius: 4px; }
.te-field input[type=text], .te-field input[type=number], .te-field select { font-size: 12px; padding: 4px 6px; }
</style>
