<template>
  <div>
    <n-space align="center" style="margin-bottom: 16px">
      <n-button text @click="$router.push('/hosts')">
        <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
        主机运维
      </n-button>
      <n-text depth="3">/</n-text>
      <n-text strong>{{ host?.name || '加载中...' }}</n-text>
      <n-tag v-if="host" :type="host.is_online ? 'success' : 'default'" size="small" round>
        {{ host.is_online ? '在线' : '离线' }}
      </n-tag>
    </n-space>

    <!-- Top metric cards: CPU / Memory / Disk / Load -->
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">CPU 使用率</n-text>
          <div style="display:flex;align-items:center;gap:12px;margin-top:8px">
            <n-progress type="circle" :percentage="cpuPercent" :color="cpuColor" :height="60" />
            <n-text strong style="font-size:18px">{{ cpuPercent }}%</n-text>
          </div>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">内存使用率</n-text>
          <div style="display:flex;align-items:center;gap:12px;margin-top:8px">
            <n-progress type="circle" :percentage="memPercent" :color="memColor" :height="60" />
            <n-text strong style="font-size:18px">{{ memPercent }}%</n-text>
          </div>
          <n-text depth="3" style="font-size:11px;margin-top:4px" v-if="latest">
            {{ latest.mem_used_mb }} / {{ latest.mem_total_mb }} MB
          </n-text>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">磁盘使用率</n-text>
          <div style="display:flex;align-items:center;gap:12px;margin-top:8px">
            <n-progress type="circle" :percentage="diskPercent" :color="diskColor" :height="60" />
            <n-text strong style="font-size:18px">{{ diskPercent }}%</n-text>
          </div>
          <n-text depth="3" style="font-size:11px;margin-top:4px" v-if="latest">
            {{ latest.disk_used_gb }} / {{ latest.disk_total_gb }} GB
          </n-text>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">系统负载</n-text>
          <div style="margin-top:8px">
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
              <n-text depth="3" style="font-size:11px">1分钟</n-text>
              <n-text strong>{{ latest?.load_1m ?? '-' }}</n-text>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
              <n-text depth="3" style="font-size:11px">5分钟</n-text>
              <n-text strong>{{ latest?.load_5m ?? '-' }}</n-text>
            </div>
            <div style="display:flex;justify-content:space-between">
              <n-text depth="3" style="font-size:11px">15分钟</n-text>
              <n-text strong>{{ latest?.load_15m ?? '-' }}</n-text>
            </div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- Second row: Network / Processes / Uptime -->
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">网络接收</n-text>
          <n-text strong style="font-size:18px;display:block;margin-top:4px">{{ formatBytes(latest?.net_rx_bytes ?? 0) }}</n-text>
          <n-text depth="3" style="font-size:11px">累计字节</n-text>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">网络发送</n-text>
          <n-text strong style="font-size:18px;display:block;margin-top:4px">{{ formatBytes(latest?.net_tx_bytes ?? 0) }}</n-text>
          <n-text depth="3" style="font-size:11px">累计字节</n-text>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">进程总数</n-text>
          <n-text strong style="font-size:18px;display:block;margin-top:4px">{{ latest?.process_count ?? '-' }}</n-text>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-text depth="3" style="font-size:12px">运行时长</n-text>
          <n-text strong style="font-size:18px;display:block;margin-top:4px">{{ formatUptime(latest?.uptime_seconds ?? 0) }}</n-text>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- History Chart -->
    <n-card size="small" title="历史趋势" style="margin-bottom:16px">
      <template #header-extra>
        <n-radio-group v-model:value="chartHours" size="small">
          <n-radio-button :value="1">1h</n-radio-button>
          <n-radio-button :value="6">6h</n-radio-button>
          <n-radio-button :value="24">24h</n-radio-button>
          <n-radio-button :value="168">7d</n-radio-button>
        </n-radio-group>
      </template>
      <div v-if="metrics.length === 0" style="text-align:center;padding:40px;color:#999">
        暂无监控数据，等待 Agent 首次上报...
      </div>
      <div v-else ref="chartEl" style="width:100%;height:240px"></div>
    </n-card>

    <!-- Agent Info + Alert Config -->
    <n-grid :cols="2" :x-gap="16">
      <n-grid-item>
        <n-card size="small" title="Agent 信息">
          <n-descriptions :column="1" label-placement="left" size="small">
            <n-descriptions-item label="版本">{{ host?.agent_version || '-' }}</n-descriptions-item>
            <n-descriptions-item label="最后上报">{{ relativeTime(host?.last_seen_at || null) }}</n-descriptions-item>
            <n-descriptions-item label="主机地址">{{ host?.hostname }}:{{ host?.port }}</n-descriptions-item>
          </n-descriptions>
          <n-space style="margin-top:12px">
            <n-button size="small" @click="handleRegenToken">重新生成 Token</n-button>
            <n-button size="small" @click="handleCopyInstallCmd">复制安装命令</n-button>
          </n-space>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small" title="告警配置">
          <n-form label-placement="left" label-width="80" size="small">
            <n-form-item label="启用告警">
              <n-switch v-model:value="alertEnabled" @update:value="saveAlertConfig" />
            </n-form-item>
            <n-form-item label="通知组">
              <n-select
                v-model:value="notificationGroupId"
                :options="groupOptions"
                placeholder="选择通知组"
                clearable
                style="width:200px"
                @update:value="saveAlertConfig"
              />
            </n-form-item>
          </n-form>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton, NIcon, NText, NTag, NSpace, NCard, NGrid, NGridItem,
  NProgress, NRadioGroup, NRadioButton, NDescriptions, NDescriptionsItem,
  NForm, NFormItem, NSwitch, NSelect, useMessage, useDialog,
} from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import { fetchHost, fetchHostMetrics, fetchLatestMetrics, regenerateAgentToken, fetchAgentToken, updateHost } from '@/api/hosts'
import type { Host, HostMetric, LatestMetric } from '@/api/hosts'
import { fetchGroups } from '@/api/notification-groups'

const route = useRoute()
const message = useMessage()
const dialog = useDialog()

const hostId = computed(() => Number(route.params.id))
const host = ref<Host | null>(null)
const metrics = ref<HostMetric[]>([])
const latest = ref<LatestMetric | null>(null)
const chartHours = ref(24)

const alertEnabled = ref(true)
const notificationGroupId = ref<number | null>(null)
const groupOptions = ref<{ label: string; value: number }[]>([])

const chartEl = ref<HTMLDivElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const cpuPercent = computed(() => host.value?.cpu_usage || 0)
const memPercent = computed(() => host.value?.mem_usage || 0)
const diskPercent = computed(() => host.value?.disk_usage || 0)

function thresholdColor(pct: number) {
  if (pct >= 90) return '#d03050'
  if (pct >= 70) return '#f0a020'
  return '#18a058'
}
const cpuColor = computed(() => thresholdColor(cpuPercent.value))
const memColor = computed(() => thresholdColor(memPercent.value))
const diskColor = computed(() => thresholdColor(diskPercent.value))

function relativeTime(val: string | null): string {
  if (!val) return '-'
  const diff = Date.now() - new Date(val).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)}分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)}小时前`
  return `${Math.floor(sec / 86400)}天前`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB'
  return (bytes / 1073741824).toFixed(2) + ' GB'
}

function formatUptime(sec: number): string {
  if (!sec) return '-'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (d > 0) return `${d}天 ${h}小时`
  if (h > 0) return `${h}小时 ${m}分钟`
  return `${m}分钟`
}

// ---- Canvas chart ----
watch([metrics, chartHours], () => {
  if (metrics.value.length === 0) return
  setTimeout(() => drawChart(), 50)
})

function drawChart() {
  const el = chartEl.value
  if (!el) return
  const w = el.clientWidth
  const h = el.clientHeight
  if (w === 0 || h === 0) return

  const padding = { top: 12, right: 20, bottom: 32, left: 40 }
  const pw = w - padding.left - padding.right
  const ph = h - padding.top - padding.bottom

  const canvas = document.createElement('canvas')
  canvas.width = w * 2
  canvas.height = h * 2
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'
  const ctx = canvas.getContext('2d')!
  ctx.scale(2, 2)

  ctx.fillStyle = '#fafafa'
  ctx.fillRect(0, 0, w, h)

  const series = [
    { key: 'cpu_percent', label: 'CPU %', color: '#18a058' },
    { key: 'mem_percent', label: 'MEM %', color: '#2080f0' },
    { key: 'disk_percent', label: 'DISK %', color: '#f0a020' },
    { key: 'load_1m', label: 'LOAD', color: '#d03050' },
  ]

  const allVals = metrics.value.flatMap((m: any) => series.map(s => m[s.key] || 0))
  const maxVal = Math.max(...allVals, 1)

  const xScale = (i: number) => padding.left + (i / (metrics.value.length - 1 || 1)) * pw
  const yScale = (v: number) => padding.top + ph - (v / maxVal) * ph

  // Grid
  ctx.strokeStyle = '#e8e8e8'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (ph * i) / 4
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(w - padding.right, y); ctx.stroke()
    ctx.fillStyle = '#999'; ctx.font = '9px sans-serif'
    ctx.fillText(Math.round(maxVal - (maxVal * i) / 4) + '', 2, y + 3)
  }

  // X-axis labels
  if (metrics.value.length > 1) {
    ctx.fillStyle = '#999'; ctx.font = '9px sans-serif'
    const step = Math.max(1, Math.floor(metrics.value.length / 6))
    for (let i = 0; i < metrics.value.length; i += step) {
      const t = (metrics.value[i] as any).collected_at
      if (!t) continue
      const d = new Date(t)
      const label = chartHours.value >= 168
        ? `${d.getMonth() + 1}/${d.getDate()}`
        : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
      ctx.fillText(label, xScale(i) - 15, h - padding.bottom + 14)
    }
  }

  // Draw lines
  for (const s of series) {
    ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.beginPath()
    for (let i = 0; i < metrics.value.length; i++) {
      const v = (metrics.value[i] as any)[s.key] || 0
      const x = xScale(i); const y = yScale(v)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.stroke()
  }

  // Legend
  let lx = padding.left
  for (const s of series) {
    ctx.fillStyle = s.color; ctx.fillRect(lx, h - 4, 10, 10)
    ctx.fillStyle = '#666'; ctx.font = '10px sans-serif'
    ctx.fillText(s.label, lx + 13, h + 5)
    lx += ctx.measureText(s.label).width + 30
  }

  el.innerHTML = ''
  el.appendChild(canvas)
}

// ---- Data loading ----
async function loadAll() {
  try {
    const [hRes, mRes, lRes] = await Promise.all([
      fetchHost(hostId.value),
      fetchHostMetrics(hostId.value, chartHours.value),
      fetchLatestMetrics(hostId.value).catch(() => null),
    ])
    host.value = hRes.data
    metrics.value = mRes.data.items || []
    if (lRes) latest.value = lRes.data
    alertEnabled.value = host.value.alert_enabled
    notificationGroupId.value = host.value.notification_group_id
  } catch (e: any) {
    message.error(e.message || '加载失败')
  }
}

async function loadGroups() {
  try {
    const resp = await fetchGroups()
    groupOptions.value = (resp.data || []).map((g: any) => ({ label: g.name, value: g.id }))
  } catch (_e) {}
}

watch(chartHours, () => loadAll())

async function saveAlertConfig() {
  try {
    await updateHost(hostId.value, {
      alert_enabled: alertEnabled.value,
      notification_group_id: notificationGroupId.value,
    })
  } catch (e: any) { message.error(e.message || '保存失败') }
}

async function handleRegenToken() {
  dialog.warning({
    title: '重新生成 Agent Token',
    content: '确定要重新生成 Token 吗？旧的 Token 将立即失效。',
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const resp = await regenerateAgentToken(hostId.value)
        dialog.success({
          title: '新 Token', content: resp.data.agent_token,
          positiveText: '复制',
          onPositiveClick: () => navigator.clipboard.writeText(resp.data.agent_token).catch(() => {}),
        })
      } catch (e: any) { message.error(e.message || '生成失败') }
    },
  })
}

async function handleCopyInstallCmd() {
  try {
    const resp = await fetchAgentToken(hostId.value)
    const origin = window.location.origin
    const cmd = `curl -fsSL https://github.com/githubliuyang777/openassassin/releases/latest/download/install.sh | bash -s -- --server ${origin} --token ${resp.data.agent_token}`
    navigator.clipboard.writeText(cmd).then(
      () => message.success('安装命令已复制'),
      () => message.warning('复制失败'),
    )
  } catch (e: any) { message.error(e.message || '获取 Token 失败') }
}

onMounted(() => { loadAll(); loadGroups(); pollTimer = setInterval(loadAll, 30000) })
onUnmounted(() => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } })
</script>
