<template>
  <div class="flex items-center gap-3 px-3 py-2.5">
    <Skeleton class="rounded-4 size-6 shrink-0" />

    <div class="flex-1 min-w-0">
      <!-- Wrappers carry the real row's line-box heights so the swap shifts nothing. -->
      <div class="flex items-center h-4">
        <Skeleton class="rounded-4 h-3" :class="titleWidth" />
      </div>
      <div class="flex items-center mt-0.5 h-5">
        <Skeleton class="rounded-4 h-2.5" :class="subtitleWidth" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Skeleton } from 'frappe-ui'

const props = defineProps({
  // Index-based width cycle: varied bars, stable across re-renders.
  index: { type: Number, default: 0 },
})

const TITLE_WIDTHS = ['w-32', 'w-40', 'w-28', 'w-36']
const SUBTITLE_WIDTHS = ['w-56', 'w-44', 'w-64', 'w-48']

const titleWidth = computed(() => TITLE_WIDTHS[props.index % TITLE_WIDTHS.length])
const subtitleWidth = computed(() => SUBTITLE_WIDTHS[props.index % SUBTITLE_WIDTHS.length])
</script>
