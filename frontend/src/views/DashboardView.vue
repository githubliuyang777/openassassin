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

    <n-card
      title="主机监控"
      :bordered="true"
      hoverable
      @click="router.push('/hosts')"
      style="margin-top: 24px; cursor: pointer"
    >
      <template #header-extra>
        <n-text type="primary">查看全部 →</n-text>
      </template>
      <n-grid :cols="4" :x-gap="16">
        <n-grid-item><n-statistic label="在线主机" :value="`${hostStats.online} / ${hostStats.total}`" /></n-grid-item>
        <n-grid-item><n-statistic label="离线主机" :value="hostStats.offline" /></n-grid-item>
        <n-grid-item><n-statistic label="平均 CPU" :value="hostStats.avgCpu > 0 ? `${hostStats.avgCpu}%` : '-'" /></n-grid-item>
        <n-grid-item><n-statistic label="平均内存" :value="hostStats.avgMem > 0 ? `${hostStats.avgMem}%` : '-'" /></n-grid-item>
      </n-grid>
    </n-card>

    <n-card
      title="站点监控"
      :bordered="true"
      hoverable
      @click="router.push('/monitor/site-monitor')"
      style="margin-top: 16px; cursor: pointer"
    >
      <template #header-extra>
        <n-text type="primary">查看全部 →</n-text>
      </template>
      <n-grid :cols="3" :x-gap="16">
        <n-grid-item><n-statistic label="总计" :value="monitorSummary.site_monitors.total" /></n-grid-item>
        <n-grid-item><n-statistic label="正常" :value="monitorSummary.site_monitors.up"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-grid-item>
        <n-grid-item><n-statistic label="故障" :value="monitorSummary.site_monitors.down"><template #suffix><n-text v-if="monitorSummary.site_monitors.down > 0" type="error">✗</n-text></template></n-statistic></n-grid-item>
      </n-grid>
    </n-card>

    <n-card
      title="域名证书"
      :bordered="true"
      hoverable
      @click="router.push('/monitor/domains')"
      style="margin-top: 16px; cursor: pointer"
    >
      <template #header-extra>
        <n-text type="primary">查看全部 →</n-text>
      </template>
      <n-grid :cols="4" :x-gap="16">
        <n-grid-item><n-statistic label="总计" :value="monitorSummary.domain_certs.total" /></n-grid-item>
        <n-grid-item><n-statistic label="有效" :value="monitorSummary.domain_certs.valid"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-grid-item>
        <n-grid-item><n-statistic label="即将过期" :value="monitorSummary.domain_certs.expiring"><template #suffix><n-text v-if="monitorSummary.domain_certs.expiring > 0" type="warning">⚠️</n-text></template></n-statistic></n-grid-item>
        <n-grid-item><n-statistic label="已过期" :value="monitorSummary.domain_certs.expired"><template #suffix><n-text v-if="monitorSummary.domain_certs.expired > 0" type="error">✗</n-text></template></n-statistic></n-grid-item>
      </n-grid>
    </n-card>

    <n-card
      title="域名监控 (WHOIS)"
      :bordered="true"
      hoverable
      @click="router.push('/monitor/domains-whois')"
      style="margin-top: 16px; cursor: pointer"
    >
      <template #header-extra>
        <n-text type="primary">查看全部 →</n-text>
      </template>
      <n-grid :cols="4" :x-gap="16">
        <n-grid-item><n-statistic label="总计" :value="monitorSummary.domain_whois.total" /></n-grid-item>
        <n-grid-item><n-statistic label="有效" :value="monitorSummary.domain_whois.valid"><template #suffix><n-text type="success">✓</n-text></template></n-statistic></n-grid-item>
        <n-grid-item><n-statistic label="即将过期" :value="monitorSummary.domain_whois.expiring"><template #suffix><n-text v-if="monitorSummary.domain_whois.expiring > 0" type="warning">⚠️</n-text></template></n-statistic></n-grid-item>
        <n-grid-item><n-statistic label="已过期" :value="monitorSummary.domain_whois.expired"><template #suffix><n-text v-if="monitorSummary.domain_whois.expired > 0" type="error">✗</n-text></template></n-statistic></n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NGrid, NGridItem, NCard, NStatistic, NText } from 'naive-ui'
import { fetchScripts } from '@/api/scripts'
import { fetchCredentials } from '@/api/credentials'
import { fetchExecutions } from '@/api/executions'
import { fetchAgentStatus } from '@/api/agents'
import { fetchMonitorSummary, type MonitorSummary } from '@/api/overview'

const router = useRouter()
const stats = reactive({ scripts: 0, credentials: 0, todayExecutions: 0, successRate: 0 })
const hostStats = reactive({ total: 0, online: 0, offline: 0, avgCpu: 0, avgMem: 0 })
const defaultMonitorSummary: MonitorSummary = {
  site_monitors: { total: 0, up: 0, down: 0, items: [] },
  domain_certs: { total: 0, valid: 0, expiring: 0, expired: 0, items: [] },
  domain_whois: { total: 0, valid: 0, expiring: 0, expired: 0, items: [] },
}
const monitorSummary = reactive<MonitorSummary>(defaultMonitorSummary)

onMounted(async () => {
  const [sRes, cRes, eRes] = await Promise.all([fetchScripts(1, 1), fetchCredentials(), fetchExecutions(1, 100)])
  stats.scripts = sRes.data.total; stats.credentials = cRes.data.length; stats.todayExecutions = eRes.data.total
  const items = eRes.data.items || []
  stats.successRate = items.length ? Math.round((items.filter((i: any) => i.status === 'success').length / items.length) * 100) : 100
  try {
    const hosts = (await fetchAgentStatus()).data || []
    hostStats.total = hosts.length
    hostStats.online = hosts.filter(h => h.is_online).length; hostStats.offline = hostStats.total - hostStats.online
    if (hosts.length > 0) { hostStats.avgCpu = Math.round(hosts.reduce((s, h) => s + (h.cpu_usage || 0), 0) / hosts.length); hostStats.avgMem = Math.round(hosts.reduce((s, h) => s + (h.mem_usage || 0), 0) / hosts.length) }
  } catch (_e) {}
  try {
    const summary = (await fetchMonitorSummary()).data
    Object.assign(monitorSummary, summary)
  } catch (_e) {}
})
</script>
