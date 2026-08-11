<template>
  <!-- text-p-sm: a log body is stacked copy; text-sm's 1.15 line-height packs
       it solid. gray-2: the solid ramp steps much harder in dark mode. -->
  <div
    ref="el"
    class="bg-surface-gray-2 overflow-auto font-mono text-ink-gray-8 text-p-sm"
    @scroll="onScroll"
    :class="[wrap ? 'whitespace-pre-wrap' : 'whitespace-pre', rounded-4 ? 'rounded-4' : '', fill ? 'flex-1 h-0' : 'max-h-[50vh]', rows ? '' : 'px-4 py-3']"
  >
    <p v-if="!lines.length" class="text-ink-gray-4" :class="rows ? 'px-4 py-3' : ''">
      {{ emptyText }}
    </p>
    <div
      v-for="(line, index) in lines"
      :key="index"
      class="flex gap-3"
      :class="rows ? 'px-2 py-1.5 sm:px-4 hover:bg-surface-gray-3' : ''"
    >
      <span
        v-if="lineNumbers"
        class="text-ink-gray-4 text-right select-none shrink-0"
        style="min-width: 1.75rem"
      >
        {{ index + 1 }}
      </span>
      <span class="flex-1" :class="wrap ? 'break-words' : ''" v-html="line || '&nbsp;'" />
    </div>
    <span
      v-if="streaming"
      class="inline-block animate-pulse"
      :class="rows ? 'px-3 py-1 sm:px-4' : ''"
      >█</span
    >
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  lines: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  lineNumbers: { type: Boolean, default: false },
  wrap: { type: Boolean, default: false },
  rounded: { type: Boolean, default: true },
  fill: { type: Boolean, default: false },
  rows: { type: Boolean, default: false },
  emptyText: { type: String, default: 'No output.' },
})

const el = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (el.value) el.value.scrollTop = el.value.scrollHeight
  })
}

// Follow the tail while streaming; scrolling up pauses it, returning to the
// bottom resumes it.
const follow = ref(true)

function onScroll() {
  const box = el.value
  if (!box) return
  follow.value = box.scrollHeight - box.scrollTop - box.clientHeight < 8
}

watch(
  () => props.streaming,
  (on) => {
    if (!on) return
    follow.value = true
    scrollToBottom()
  },
  { immediate: true },
)

watch(
  () => props.lines.length,
  () => {
    if (props.streaming && follow.value) scrollToBottom()
  },
)

defineExpose({ scrollToBottom })
</script>
