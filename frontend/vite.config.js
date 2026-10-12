import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue2'

// dev 模式把 API 与音频目录代理到 3090 后端，使 hydrate() 走真实数据
// 覆盖目标：VITE_API_TARGET=http://192.168.31.213:4200 npm run dev
const TARGET = process.env.VITE_API_TARGET || 'http://192.168.31.213:4200'

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    proxy: Object.fromEntries(
      ['/api', '/voicelines', '/designed_voices', '/clone_voices', '/lora_models', '/builtin_lora', '/dataset_builder', '/static']
        .map((p) => [p, { target: TARGET, changeOrigin: true }])
    )
  }
})
