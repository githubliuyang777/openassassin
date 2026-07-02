<template>
  <n-modal
    :show="visible"
    :mask-closable="false"
    :closable="false"
    title="安全验证"
    preset="card"
    style="width: 400px"
  >
    <div class="captcha-box">
      <div
        ref="trackRef"
        class="slider-track"
        :class="{ 'slider-track--success': status === 'success', 'slider-track--failed': status === 'failed' }"
      >
        <div
          class="slider-fill"
          :class="{ 'slider-fill--success': status === 'success', 'slider-fill--failed': status === 'failed' }"
          :style="{ width: fillWidth + 'px' }"
        />
        <span v-if="status !== 'dragging' && status !== 'verifying'" class="slider-label">
          <n-spin v-if="status === 'loading'" :size="16" />
          <template v-else-if="status === 'ready' || status === 'failed'">请向右滑动滑块完成验证</template>
          <template v-else-if="status === 'success'">验证通过</template>
        </span>
        <div
          class="slider-handle"
          :class="{ 'slider-handle--dragging': dragging }"
          :style="{ left: handleLeft + 'px' }"
          @mousedown.prevent="startDrag"
          @touchstart.prevent="startDrag"
        >
          <svg v-if="status === 'success'" viewBox="0 0 24 24" width="20" height="20" fill="#18a058">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="#999">
            <path d="M14 6v2h4v12H6V8h4V6H4v16h16V6h-6zm-2 2V2h2v6h-2z" />
          </svg>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'
import { NModal, NSpin } from 'naive-ui'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'verified', token: string): void
}>()

type Status = 'loading' | 'ready' | 'dragging' | 'verifying' | 'success' | 'failed'

const TRACK_WIDTH = 300
const HANDLE_SIZE = 40
const MAX_LEFT = TRACK_WIDTH - HANDLE_SIZE

const status = ref<Status>('loading')
const dragging = ref(false)
const handleLeft = ref(0)
const fillWidth = ref(0)
const captchaToken = ref('')
const trackRef = ref<HTMLElement | null>(null)

let startClientX = 0
let startHandleLeft = 0

function resetSlider() {
  handleLeft.value = 0
  fillWidth.value = 0
  dragging.value = false
  status.value = 'ready'
}

async function initCaptcha() {
  status.value = 'loading'
  try {
    const resp = await axios.post('/api/v1/auth/captcha/generate')
    captchaToken.value = resp.data.captcha_token
    resetSlider()
  } catch {
    status.value = 'failed'
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    initCaptcha()
  }
})

function startDrag(e: MouseEvent | TouchEvent) {
  if (status.value !== 'ready' && status.value !== 'failed') return
  dragging.value = true
  status.value = 'dragging'
  startHandleLeft = handleLeft.value
  startClientX = e instanceof MouseEvent ? e.clientX : e.touches[0].clientX
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onEnd)
  window.addEventListener('touchmove', onMove, { passive: false })
  window.addEventListener('touchend', onEnd)
}

function onMove(e: MouseEvent | TouchEvent) {
  if (!dragging.value) return
  e.preventDefault()
  const clientX = e instanceof MouseEvent ? e.clientX : e.touches[0].clientX
  const delta = clientX - startClientX
  const left = Math.max(0, Math.min(MAX_LEFT, startHandleLeft + delta))
  handleLeft.value = left
  fillWidth.value = left + HANDLE_SIZE / 2
}

function onEnd() {
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onEnd)
  window.removeEventListener('touchmove', onMove)
  window.removeEventListener('touchend', onEnd)
  if (!dragging.value) return
  dragging.value = false

  const userX = Math.round(handleLeft.value + HANDLE_SIZE / 2)
  if (userX < 10) {
    resetSlider()
    return
  }
  verifyWithBackend(userX)
}

async function verifyWithBackend(userX: number) {
  status.value = 'verifying'
  try {
    const resp = await axios.post('/api/v1/auth/captcha/verify', {
      captcha_token: captchaToken.value,
      user_x: userX,
    })
    if (resp.data.success) {
      status.value = 'success'
      setTimeout(() => {
        emit('verified', resp.data.verification_token)
        emit('update:visible', false)
      }, 600)
    } else {
      status.value = 'failed'
      setTimeout(() => resetSlider(), 800)
    }
  } catch {
    status.value = 'failed'
    setTimeout(() => resetSlider(), 800)
  }
}
</script>

<style scoped>
.captcha-box {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}

.slider-track {
  width: 300px;
  height: 40px;
  background: #e8e8e8;
  border-radius: 20px;
  position: relative;
  overflow: hidden;
  user-select: none;
}

.slider-track::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  width: 80px;
  height: 100%;
  background: linear-gradient(to right, transparent, rgba(24, 160, 88, 0.12));
  border-radius: 0 20px 20px 0;
  pointer-events: none;
  z-index: 0;
}

.slider-track--success {
  background: #e8f8ef;
}

.slider-track--failed {
  background: #fde8ec;
}

.slider-fill {
  height: 100%;
  background: #18a058;
  border-radius: 20px 0 0 20px;
  position: absolute;
  left: 0;
  top: 0;
  transition: width 0.05s linear;
}

.slider-fill--success {
  background: #18a058;
}

.slider-fill--failed {
  background: #d03050;
}

.slider-label {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #999;
  pointer-events: none;
  z-index: 1;
}

.slider-handle {
  width: 40px;
  height: 40px;
  background: #fff;
  border: 2px solid #d9d9d9;
  border-radius: 50%;
  cursor: grab;
  position: absolute;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}

.slider-handle--dragging {
  border-color: #18a058;
  box-shadow: 0 0 0 3px rgba(24, 160, 88, 0.2);
}

.slider-handle:active {
  cursor: grabbing;
}
</style>
