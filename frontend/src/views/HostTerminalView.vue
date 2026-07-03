<template>
  <div style="display: flex; flex-direction: column; height: calc(100vh - 140px)">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; flex-shrink: 0">
      <n-space align="center">
        <n-button text @click="goBack">
          <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
          返回
        </n-button>
        <n-tag type="info" size="small">{{ host?.name || '加载中...' }}</n-tag>
        <n-text depth="3" style="font-size: 12px">{{ host ? `${host.hostname}:${host.port}` : '' }}</n-text>
      </n-space>
      <n-space>
        <n-tag v-if="status === 'connected'" type="success" size="small">已连接</n-tag>
        <n-tag v-else-if="status === 'connecting'" type="warning" size="small">连接中...</n-tag>
        <n-tag v-else type="default" size="small">未连接</n-tag>
        <n-button v-if="status === 'disconnected'" size="small" type="primary" @click="doConnect">重新连接</n-button>
        <n-button size="small" @click="goBack">断开</n-button>
      </n-space>
    </div>

    <div style="flex: 1; position: relative; background: #1e1e1e; border-radius: 4px; overflow: hidden">
      <div ref="termRef" style="width: 100%; height: 100%"></div>
      <div v-if="status === 'disconnected'" style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.7); gap: 12px">
        <n-text style="color: #fff; font-size: 16px">连接已断开</n-text>
        <n-text v-if="errorMsg" style="color: #e88080; font-size: 13px">{{ errorMsg }}</n-text>
        <n-button type="primary" @click="doConnect">重新连接</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, NTag, NButton, NIcon, NSpace, NText } from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useAuthStore } from '@/stores/auth'
import { fetchHost } from '@/api/hosts'
import type { Host } from '@/api/hosts'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const auth = useAuthStore()

const termRef = ref<HTMLDivElement>()
const status = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
const errorMsg = ref('')
const host = ref<Host | null>(null)

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let ws: WebSocket | null = null
let resizeObserver: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

function goBack() {
  cleanup()
  router.push('/hosts')
}

function cleanup() {
  if (ws) {
    ws.close()
    ws = null
  }
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
  if (resizeTimer) {
    clearTimeout(resizeTimer)
    resizeTimer = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  status.value = 'disconnected'
}

async function doConnect() {
  const hostId = route.params.id as string
  if (!hostId) return

  try {
    const resp = await fetchHost(Number(hostId))
    host.value = resp.data
  } catch (_e) { /* ignore */ }

  errorMsg.value = ''
  status.value = 'connecting'
  cleanup()

  if (!termRef.value) return

  terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: { background: '#1e1e1e', foreground: '#d4d4d4' },
    allowProposedApi: true,
  })
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(termRef.value)

  nextTick(() => {
    if (fitAddon && termRef.value) {
      try { fitAddon.fit() } catch (_e) { /* ignore */ }
    }
  })

  let resizeTimer: ReturnType<typeof setTimeout> | null = null
  resizeObserver = new ResizeObserver(() => {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      if (fitAddon) {
        try { fitAddon.fit() } catch (_e) { /* ignore */ }
        if (terminal && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }))
        }
      }
    }, 100)
  })
  resizeObserver.observe(termRef.value)

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${location.host}/api/v1/hosts/${hostId}/terminal?token=${auth.token}`

  ws = new WebSocket(wsUrl)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    status.value = 'connected'
    if (terminal && fitAddon) {
      try { fitAddon.fit() } catch (_e) { /* ignore */ }
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }))
      }
    }
  }

  ws.onmessage = (event) => {
    if (terminal) {
      if (event.data instanceof ArrayBuffer) {
        terminal.write(new Uint8Array(event.data))
      } else if (typeof event.data === 'string') {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'error') {
            message.error(msg.message)
            errorMsg.value = msg.message
          }
        } catch (_e) {
          terminal.write(event.data)
        }
      }
    }
  }

  ws.onerror = () => {
    status.value = 'disconnected'
    errorMsg.value = 'WebSocket 连接失败'
  }

  ws.onclose = (event) => {
    status.value = 'disconnected'
    if (event.code === 4001) errorMsg.value = '认证失败，请重新登录'
    else if (event.code === 4000) errorMsg.value = `SSH 连接失败: ${event.reason || '未知错误'}`
    else if (event.code !== 1000) errorMsg.value = `连接关闭 (code: ${event.code})`
  }

  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
    }
  })
}

onMounted(doConnect)

onUnmounted(() => {
  cleanup()
})
</script>
