<script setup lang="ts">
import { ref } from 'vue'

defineProps({
  label: { type: String, required: true },
  subLabel: { type: String, default: '' },
})

const isVisible = ref(false)
</script>

<template>
  <div class="border rounded-4 text-base">
    <div
      class="flex flex-row justify-between items-center gap-2 p-4 cursor-pointer select-none"
      :class="{ '!pb-2': isVisible }"
      @click="isVisible = !isVisible"
    >
      <div>
        <p class="font-medium text-ink-gray-8">{{ label }}</p>
        <p v-if="subLabel" class="mt-2 text-ink-gray-7 text-sm">{{ subLabel }}</p>
      </div>

      <div v-if="isVisible" @click.stop>
        <slot name="actions" />
      </div>
    </div>

    <div v-if="isVisible" class="text-sm leading-normal">
      <slot />
    </div>
  </div>
</template>
