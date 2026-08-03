<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">EC2 实例</n-h3>
      <n-space>
        <n-select
          v-model:value="selectedCredentialId"
          :options="credentialOptions"
          placeholder="选择 AWS 凭证"
          style="width: 200px"
          @update:value="loadInstances"
        />
        <n-select
          v-model:value="selectedRegion"
          :options="regionOptions"
          placeholder="选择区域"
          style="width: 180px"
          @update:value="loadInstances"
        />
        <n-button :loading="loading" @click="loadInstances">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新
        </n-button>
      </n-space>
    </n-space>

    <n-data-table
      :columns="columns"
      :data="instances"
      :loading="loading"
      :row-key="(r: Ec2Instance) => r.instance_id"
      size="small"
    />

    <!-- Action Confirmation Dialog -->
    <n-modal v-model:show="showActionConfirm" preset="card" title="确认操作" style="width: 400px">
      <p>
        确定要对实例 <strong>{{ actionTarget?.name }}</strong>
        ({{ actionTarget?.instance_id }}) 执行
        <n-tag :type="actionTagType">{{ actionLabel }}</n-tag> 操作？
      </p>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showActionConfirm = false">取消</n-button>
          <n-button type="primary" :loading="acting" @click="confirmAction">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Instance Detail Drawer (optional, not yet wired) -->
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed, onMounted } from 'vue'
import {
  NH3, NSpace, NButton, NIcon, NDataTable, NSelect, NModal, NTag, useDialog, useMessage,
} from 'naive-ui'
import { RefreshOutline, PlayOutline, StopOutline } from '@vicons/ionicons5'
import type { DataTableColumn } from 'naive-ui'
import { fetchCredentials, getTypeLabel } from '@/api/credentials'
import {
  fetchRegions,
  fetchInstances,
  instanceAction,
  type Ec2Instance,
} from '@/api/aws'

const dialog = useDialog()
const message = useMessage()

// -- state ----------------------------------------------------------------

const loading = ref(false)
const acting = ref(false)
const instances = ref<Ec2Instance[]>([])
const regions = ref<string[]>([])
const awsCredentials = ref<{ id: number; name: string }[]>([])
const selectedCredentialId = ref<number | null>(null)
const selectedRegion = ref<string | null>(null)
const showActionConfirm = ref(false)
const actionTarget = ref<Ec2Instance | null>(null)
const pendingAction = ref<'start' | 'stop' | 'reboot'>('stop')

// -- computed -------------------------------------------------------------

const credentialOptions = computed(() =>
  awsCredentials.value.map(c => ({ label: c.name, value: c.id })),
)

const regionOptions = computed(() =>
  regions.value.map(r => ({ label: r, value: r })),
)

const actionLabel = computed(() => {
  const map: Record<string, string> = { start: '启动', stop: '停止', reboot: '重启' }
  return map[pendingAction.value] || pendingAction.value
})

const actionTagType = computed(() => {
  if (pendingAction.value === 'start') return 'success' as const
  if (pendingAction.value === 'stop') return 'error' as const
  return 'warning' as const
})

// -- columns --------------------------------------------------------------

const columns: DataTableColumn<Ec2Instance>[] = [
  { title: '名称', key: 'name', width: 180, ellipsis: { tooltip: true } },
  { title: '实例 ID', key: 'instance_id', width: 160, ellipsis: { tooltip: true } },
  { title: '类型', key: 'instance_type', width: 110 },
  {
    title: '状态', key: 'state', width: 90,
    render: (r) => {
      const color = r.state === 'running' ? 'success' : r.state === 'stopped' ? 'error' : 'warning'
      return h(NTag, { type: color, size: 'small' }, () => r.state)
    },
  },
  { title: '私有 IP', key: 'private_ip', width: 130 },
  { title: '公有 IP', key: 'public_ip', width: 130 },
  { title: '可用区', key: 'availability_zone', width: 130 },
  {
    title: '操作', key: 'actions', width: 220,
    render: (r) => {
      const btns: any[] = []
      if (r.state === 'stopped') {
        btns.push(
          h(NButton, {
            size: 'tiny', type: 'success', secondary: true,
            style: { marginRight: '6px' },
            onClick: () => triggerAction(r, 'start'),
          }, () => '启动'),
        )
      }
      if (r.state === 'running') {
        btns.push(
          h(NButton, {
            size: 'tiny', type: 'warning', secondary: true,
            style: { marginRight: '6px' },
            onClick: () => triggerAction(r, 'stop'),
          }, () => '停止'),
        )
        btns.push(
          h(NButton, {
            size: 'tiny', type: 'error', secondary: true,
            onClick: () => triggerAction(r, 'reboot'),
          }, () => '重启'),
        )
      }
      return h(NSpace, { size: 4 }, () => btns)
    },
  },
]

// -- lifecycle ------------------------------------------------------------

onMounted(async () => {
  await loadCredentials()
  await loadRegions()
})

// -- methods --------------------------------------------------------------

async function loadCredentials() {
  try {
    const resp = await fetchCredentials()
    awsCredentials.value = (resp.data || [])
      .filter((c: any) => c.type === 'aws')
      .map((c: any) => ({ id: c.id, name: `${c.name} (${getTypeLabel(c.type)})` }))
    if (awsCredentials.value.length > 0 && !selectedCredentialId.value) {
      selectedCredentialId.value = awsCredentials.value[0].id
    }
  } catch (_e) { /* ignore */ }
}

async function loadRegions() {
  try {
    const resp = await fetchRegions()
    regions.value = resp.data.regions || []
    if (regions.value.length > 0 && !selectedRegion.value) {
      selectedRegion.value = regions.value[0]
    }
  } catch (_e) { /* ignore */ }
}

async function loadInstances() {
  if (!selectedCredentialId.value || !selectedRegion.value) return
  loading.value = true
  try {
    const resp = await fetchInstances(selectedCredentialId.value, selectedRegion.value)
    instances.value = resp.data || []
  } catch (e: any) {
    message.error(e.message || '加载 EC2 实例失败')
  } finally {
    loading.value = false
  }
}

function triggerAction(inst: Ec2Instance, action: 'start' | 'stop' | 'reboot') {
  actionTarget.value = inst
  pendingAction.value = action
  showActionConfirm.value = true
}

async function confirmAction() {
  if (!actionTarget.value || !selectedCredentialId.value || !selectedRegion.value) return
  acting.value = true
  try {
    const resp = await instanceAction(
      actionTarget.value.instance_id,
      selectedCredentialId.value,
      selectedRegion.value,
      pendingAction.value,
    )
    message.success(
      `${actionTarget.value.name} ${actionLabel.value}成功 → ${resp.data.new_state}`,
    )
    showActionConfirm.value = false
    await loadInstances()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  } finally {
    acting.value = false
  }
}
</script>
