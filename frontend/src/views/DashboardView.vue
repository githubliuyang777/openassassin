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
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { NH3, NGrid, NGridItem, NCard, NStatistic } from 'naive-ui'
import { fetchScripts } from '@/api/scripts'
import { fetchCredentials } from '@/api/credentials'
import { fetchExecutions } from '@/api/executions'

const stats = reactive({
  scripts: 0,
  credentials: 0,
  todayExecutions: 0,
  successRate: 0,
})

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
})
</script>
