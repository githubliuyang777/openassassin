<template>
  <div>
    <n-h3>概览</n-h3>
    <n-grid :cols="4" :x-gap="16">
      <n-grid-item>
        <n-card>
          <n-statistic label="脚本总数" :value="stats.scripts" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card>
          <n-statistic label="密钥总数" :value="stats.credentials" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card>
          <n-statistic label="今日执行" :value="stats.todayExecutions" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card>
          <n-statistic label="成功率" :value="`${stats.successRate}%`" />
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- Host monitoring overview -->
    <n-h3 style="margin-top: 28px">主机监控</n-h3>
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item>
        <n-card size="small">
          <n-statistic label="在线主机" :value="`${hostStats.online} / ${hostStats.total}`" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-statistic label="离线主机" :value="hostStats.offline" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-statistic label="平均 CPU" :value="hostStats.avgCpu > 0 ? `${hostStats.avgCpu}%` : '-'" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card size="small">
          <n-statistic label="平均内存" :value="hostStats.avgMem > 0 ? `${hostStats.avgMem}%` : '-'" />
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-data-table
      v-if="hostStatusList.length > 0"
      :columns="hostColumns"
      :data="hostStatusList"
      :row-key="(r: any) => r.id"
      size="small"
      :bordered="false"
    />
    <n-text v-else depth="3" style="display:block;text-align:center;padding:24px">
      暂无主机数据，请先在「主机运维」中添加主机
    </n-text>
  </div>
</template>

<script setup lang="ts">
import { h, reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NH3, NGrid, NGridItem, NCard, NStatistic, NDataTable, NText, NTag, NProgress,
} from 'naive-ui'
import { fetchScripts } from '@/api/scripts'
import { fetchCredentials } from '@/api/credentials'
import { fetchExecutions } from '@/api/executions'
import { fetchAgentStatus, type HostAgentStatus } from '@/api/agents'
import type { DataTableColumn } from 'naive-ui'

const router = useRouter()

const stats = reactive({
  scripts: 0,
  credentials: 0,
  todayExecutions: 0,
  successRate: 0,
})

const hostStats = reactive({
  total: 0,
  online: 0,
  offline: 0,
  avgCpu: 0,
  avgMem: 0,
})

const hostStatusList = ref<HostAgentStatus[]>([])

const hostColumns: DataTableColumn<HostAgentStatus>[] = [
  {
    title: '名称', key: 'name', width: 150,
    render: (r) => h('a', {
      style: 'color:#2080f0;cursor:pointer',
      onClick: () => router.push(`/hosts/${r.id}`),
    }, r.name),
  },
  {
    title: '状态', key: 'is_online', width: 70,
    render: (r) => h(NTag, { type: r.is_online ? 'success' : 'default', size: 'small', round: true },
      () => r.is_online ? '在线' : '离线'),
  },
  {
    title: 'CPU', key: 'cpu_usage', width: 120,
    render: (r) => {
      const pct = r.cpu_usage || 0
      const color = pct >= 90 ? '#d03050' : pct >= 70 ? '#f0a020' : '#18a058'
      return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [
        h(NProgress, { percentage: pct, color, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }),
        h('span', { style: 'font-size:12px' }, `${pct}%`),
      ])
    },
  },
  {
    title: '内存', key: 'mem_usage', width: 120,
    render: (r) => {
      const pct = r.mem_usage || 0
      const color = pct >= 90 ? '#d03050' : pct >= 70 ? '#f0a020' : '#18a058'
      return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [
        h(NProgress, { percentage: pct, color, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }),
        h('span', { style: 'font-size:12px' }, `${pct}%`),
      ])
    },
  },
  {
    title: '磁盘', key: 'disk_usage', width: 120,
    render: (r) => {
      const pct = r.disk_usage || 0
      const color = pct >= 90 ? '#d03050' : pct >= 85 ? '#f0a020' : '#18a058'
      return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [
        h(NProgress, { percentage: pct, color, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }),
        h('span', { style: 'font-size:12px' }, `${pct}%`),
      ])
    },
  },
]

onMounted(async () => {
  const [sRes, cRes, eRes] = await Promise.all([
    fetchScripts(1, 1),
    fetchCredentials(),
    fetchExecutions(1, 100),
  ])
  stats.scripts = sRes.data.total
  stats.credentials = cRes.data.length
  stats.todayExecutions = eRes.data.total
  const items = eRes.data.items || []
  const success = items.filter((i: any) => i.status === 'success').length
  stats.successRate = items.length ? Math.round((success / items.length) * 100) : 100

  try {
    const resp = await fetchAgentStatus()
    const hosts = resp.data || []
    hostStatusList.value = hosts
    hostStats.total = hosts.length
    hostStats.online = hosts.filter(h => h.is_online).length
    hostStats.offline = hostStats.total - hostStats.online
    if (hosts.length > 0) {
      hostStats.avgCpu = Math.round(hosts.reduce((s, h) => s + (h.cpu_usage || 0), 0) / hosts.length)
      hostStats.avgMem = Math.round(hosts.reduce((s, h) => s + (h.mem_usage || 0), 0) / hosts.length)
    }
  } catch (_e) { /* non-critical */ }
})
</script>
