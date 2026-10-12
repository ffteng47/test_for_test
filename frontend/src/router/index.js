import Vue from 'vue'
import VueRouter from 'vue-router'
import ImportView from '../views/ImportView.vue'
import ScriptView from '../views/ScriptView.vue'
import CastView from '../views/CastView.vue'
import VoiceLabView from '../views/VoiceLabView.vue'
import VaultView from '../views/VaultView.vue'
import StudioView from '../views/StudioView.vue'
import ExportView from '../views/ExportView.vue'

Vue.use(VueRouter)

export default new VueRouter({
  mode: 'hash',
  routes: [
    { path: '/', redirect: '/script' },
    { path: '/import', component: ImportView, meta: { step: 1 } },
    { path: '/script', component: ScriptView, meta: { step: 2 } },
    { path: '/cast', component: CastView, meta: { step: 3 } },
    { path: '/voice-lab', component: VoiceLabView, meta: { step: 3 } },
    { path: '/vault', component: VaultView, meta: { step: 3 } },
    { path: '/studio', component: StudioView, meta: { step: 4 } },
    { path: '/export', component: ExportView, meta: { step: 5 } }
  ]
})
