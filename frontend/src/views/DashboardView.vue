<template>
  <div>
    <n-h3>概览</n-h3>
    <n-grid :cols="4" :x-gap="16">
      <n-grid-item><n-card><n-statistic label="脚本总数" :value="stats.scripts" /></n-card></n-grid-item>
      <n-grid-item><n-card><n-statistic label="密钥总数" :value="stats.credentials" /></n-card></n-grid-item>
      <n-grid-item><n-card><n-statistic label="今日执行" :value="stats.todayExecutions" /></n-card></n-grid-item>
      <n-grid-item><n-card><n-statistic label="成功率" :value="`${stats.successRate}%`" /></n-card></n-grid-item>
    </n-grid>

    <n-h3 style="margin-top: 28px">主机监控</n-h3>
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item><n-card size="small"><n-statistic label="在线主机" :value="`${hostStats.online} / ${hostStats.total}`" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="离线主机" :value="hostStats.offline" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="平均 CPU" :value="hostStats.avgCpu > 0 ? `${hostStats.avgCpu}%` : '-'" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="平均内存" :value="hostStats.avgMem > 0 ? `${hostStats.avgMem}%` : '-'" /></n-card></n-grid-item>
    </n-grid>

    <n-data-table v-if="hostStatusList.length > 0" :columns="hostColumns" :data="hostStatusList"
      :row-key="(r: any) => r.id" size="small" :bordered="false" />
    <n-text v-else depth="3" style="display:block;text-align:center;padding:24px">
      暂无主机数据，请先在「主机运维」中添加主机
    </n-text>

    <n-h3 style="margin-top: 28px">站点监控</n-h3>
    <n-grid :cols="3" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item><n-card size="small"><n-statistic label="总计" :value="monitorSummary.site_monitors.total" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="正常" :value="monitorSummary.site_monitors.up"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="故障" :value="monitorSummary.site_monitors.down"><template #suffix><n-text v-if="monitorSummary.site_monitors.down > 0" type="error">✗</n-text></template></n-statistic></n-card></n-grid-item>
    </n-grid>
    <n-data-table v-if="monitorSummary.site_monitors.items.length > 0" :columns="siteMonitorColumns" :data="monitorSummary.site_monitors.items"
      :row-key="(r: any) => r.id" size="small" :bordered="false" />
    <n-text v-else depth="3" style="display:block;text-align:center;padding:16px">
      暂无站点监控数据
    </n-text>

    <n-h3 style="margin-top: 28px">域名证书</n-h3>
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item><n-card size="small"><n-statistic label="总计" :value="monitorSummary.domain_certs.total" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="有效" :value="monitorSummary.domain_certs.valid"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="即将过期" :value="monitorSummary.domain_certs.expiring"><template #suffix><n-text v-if="monitorSummary.domain_certs.expiring > 0" type="warning">⚠️</n-text></template></n-statistic></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="已过期" :value="monitorSummary.domain_certs.expired"><template #suffix><n-text v-if="monitorSummary.domain_certs.expired > 0" type="error">✗</n-text></template></n-statistic></n-card></n-grid-item>
    </n-grid>
    <n-data-table v-if="monitorSummary.domain_certs.items.length > 0" :columns="domainCertColumns" :data="monitorSummary.domain_certs.items"
      :row-key="(r: any) => r.id" size="small" :bordered="false" />
    <n-text v-else depth="3" style="display:block;text-align:center;padding:16px">
      暂无域名证书数据
    </n-text>

    <n-h3 style="margin-top: 28px">域名监控 (WHOIS)</n-h3>
    <n-grid :cols="4" :x-gap="16" style="margin-bottom: 16px">
      <n-grid-item><n-card size="small"><n-statistic label="总计" :value="monitorSummary.domain_whois.total" /></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="有效" :value="monitorSummary.domain_whois.valid"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="即将过期" :value="monitorSummary.domain_whois.expiring"><template #suffix><n-text v-if="monitorSummary.domain_whois.expiring > 0" type="warning">⚠️</n-text></template></n-statistic></n-card></n-grid-item>
      <n-grid-item><n-card size="small"><n-statistic label="已过期" :value="monitorSummary.domain_whois.expired"><template #suffix><n-text v-if="monitorSummary.domain_whois.expired > 0" type="error">✗</n-text></template></n-statistic></n-card></n-grid-item>
    </n-grid>
    <n-data-table v-if="monitorSummary.domain_whois.items.length > 0" :columns="domainWhoisColumns" :data="monitorSummary.domain_whois.items"
      :row-key="(r: any) => r.id" size="small" :bordered="false" />
    <n-text v-else depth="3" style="display:block;text-align:center;padding:16px">
      暂无域名监控数据
    </n-text>
  </div>
</template>

<script setup lang="ts">
import { h, reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NH3, NGrid, NGridItem, NCard, NStatistic, NDataTable, NText, NTag, NProgress } from 'naive-ui'
import { fetchScripts } from '@/api/scripts'
import { fetchCredentials } from '@/api/credentials'
import { fetchExecutions } from '@/api/executions'
import { fetchAgentStatus, type HostAgentStatus } from '@/api/agents'
import { fetchMonitorSummary, type SiteMonitorSummary, type DomainCertSummary, type DomainWhoisSummary, type MonitorSummary } from '@/api/overview'
import type { DataTableColumn } from 'naive-ui'

const router = useRouter()
const stats = reactive({ scripts: 0, credentials: 0, todayExecutions: 0, successRate: 0 })
const hostStats = reactive({ total: 0, online: 0, offline: 0, avgCpu: 0, avgMem: 0 })
const hostStatusList = ref<HostAgentStatus[]>([])
const defaultMonitorSummary: MonitorSummary = {
  site_monitors: { total: 0, up: 0, down: 0, items: [] },
  domain_certs: { total: 0, valid: 0, expiring: 0, expired: 0, items: [] },
  domain_whois: { total: 0, valid: 0, expiring: 0, expired: 0, items: [] },
}
const monitorSummary = reactive<MonitorSummary>(defaultMonitorSummary)

const hostColumns: DataTableColumn<HostAgentStatus>[] = [
  { title: '名称', key: 'name', width: 150, render: (r) => h('a', { style: 'color:#2080f0;cursor:pointer', onClick: () => router.push(`/hosts/${r.id}`) }, r.name) },
  { title: '状态', key: 'is_online', width: 70, render: (r) => h(NTag, { type: r.is_online ? 'success' : 'default', size: 'small', round: true }, () => r.is_online ? '在线' : '离线') },
  { title: 'CPU', key: 'cpu_usage', width: 120, render: (r) => { const p = r.cpu_usage || 0; const c = p >= 90 ? '#d03050' : p >= 70 ? '#f0a020' : '#18a058'; return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [h(NProgress, { percentage: p, color: c, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }), h('span', { style: 'font-size:12px' }, `${p}%`)]) } },
  { title: '内存', key: 'mem_usage', width: 120, render: (r) => { const p = r.mem_usage || 0; const c = p >= 90 ? '#d03050' : p >= 70 ? '#f0a020' : '#18a058'; return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [h(NProgress, { percentage: p, color: c, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }), h('span', { style: 'font-size:12px' }, `${p}%`)]) } },
  { title: '磁盘', key: 'disk_usage', width: 120, render: (r) => { const p = r.disk_usage || 0; const c = p >= 90 ? '#d03050' : p >= 85 ? '#f0a020' : '#18a058'; return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [h(NProgress, { percentage: p, color: c, height: 6, style: 'flex:1;min-width:60px', showIndicator: false, borderRaius: 3 }), h('span', { style: 'font-size:12px' }, `${p}%`)]) } },
]

const siteMonitorColumns: DataTableColumn<SiteMonitorSummary>[] = [
  { title: '名称', key: 'name', width: 150, render: (r) => h('a', { style: 'color:#2080f0;cursor:pointer', onClick: () => router.push('/monitor/site-monitor') }, r.name) },
  { title: '目标', key: 'target', width: 200, ellipsis: { tooltip: true } },
  { title: '状态', key: 'is_up', width: 70, render: (r) => h(NTag, { type: r.is_up ? 'success' : 'error', size: 'small', round: true }, () => r.is_up ? '正常' : '故障') },
  { title: '响应时间', key: 'response_ms', width: 100, render: (r) => r.response_ms !== null ? `${r.response_ms}ms` : '-' },
]

const domainCertColumns: DataTableColumn<DomainCertSummary>[] = [
  { title: '域名', key: 'domain', width: 200, render: (r) => h('a', { style: 'color:#2080f0;cursor:pointer', onClick: () => router.push('/monitor/domains') }, r.domain) },
  { title: '状态', key: 'ssl_expired', width: 100, render: (r) => {
    if (r.ssl_expired) return h(NTag, { type: 'error', size: 'small', round: true }, () => '已过期')
    if (r.days_remaining !== null && r.days_remaining <= 30) return h(NTag, { type: 'warning', size: 'small', round: true }, () => '即将过期')
    return h(NTag, { type: 'success', size: 'small', round: true }, () => '有效')
  }},
  { title: '剩余天数', key: 'days_remaining', width: 100, render: (r) => r.days_remaining !== null ? (r.days_remaining > 0 ? `${r.days_remaining} 天` : '已过期') : '-' },
]

const domainWhoisColumns: DataTableColumn<DomainWhoisSummary>[] = [
  { title: '域名', key: 'domain', width: 200, render: (r) => h('a', { style: 'color:#2080f0;cursor:pointer', onClick: () => router.push('/monitor/domains-whois') }, r.domain) },
  { title: '状态', key: 'days_remaining', width: 100, render: (r) => {
    if (r.days_remaining !== null && r.days_remaining <= 0) return h(NTag, { type: 'error', size: 'small', round: true }, () => '已过期')
    if (r.days_remaining !== null && r.days_remaining <= 30) return h(NTag, { type: 'warning', size: 'small', round: true }, () => '即将过期')
    return h(NTag, { type: 'success', size: 'small', round: true }, () => '有效')
  }},
  { title: '剩余天数', key: 'days_remaining', width: 100, render: (r) => r.days_remaining !== null ? (r.days_remaining > 0 ? `${r.days_remaining} 天` : '已过期') : '-' },
]

onMounted(async () => {
  const [sRes, cRes, eRes] = await Promise.all([fetchScripts(1, 1), fetchCredentials(), fetchExecutions(1, 100)])
  stats.scripts = sRes.data.total; stats.credentials = cRes.data.length; stats.todayExecutions = eRes.data.total
  const items = eRes.data.items || []
  stats.successRate = items.length ? Math.round((items.filter((i: any) => i.status === 'success').length / items.length) * 100) : 100
  try {
    const hosts = (await fetchAgentStatus()).data || []
    hostStatusList.value = hosts; hostStats.total = hosts.length
    hostStats.online = hosts.filter(h => h.is_online).length; hostStats.offline = hostStats.total - hostStats.online
    if (hosts.length > 0) { hostStats.avgCpu = Math.round(hosts.reduce((s, h) => s + (h.cpu_usage || 0), 0) / hosts.length); hostStats.avgMem = Math.round(hosts.reduce((s, h) => s + (h.mem_usage || 0), 0) / hosts.length) }
  } catch (_e) {}
  try {
    const summary = (await fetchMonitorSummary()).data
    Object.assign(monitorSummary, summary)
  } catch (_e) {}
})
</script>
