<template>
  <component
    :is="interactive ? 'button' : 'div'"
    :type="interactive ? 'button' : null"
    class="flex items-center gap-2.5 p-2.5 rounded min-w-0 text-left"
    :class="[stateClass, interactive && 'transition duration-150 ease-[var(--ease-out)] active:scale-[0.98]']"
    :disabled="interactive && disabled ? true : null"
  >
    <span class="size-4 text-ink-gray-6 shrink-0" :class="icon" />
    <p class="flex-1 text-ink-gray-8 text-base truncate">{{ label }}</p>
    <slot name="suffix" />
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  icon: { type: String, default: 'lucide-globe' },
  selected: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  interactive: { type: Boolean, default: true },
})

const stateClass = computed(() => {
  if (props.disabled) return 'opacity-60 cursor-not-allowed'
  if (props.selected) return 'bg-surface-gray-3'
  return props.interactive ? 'hover:bg-surface-gray-2' : ''
})
</script>
