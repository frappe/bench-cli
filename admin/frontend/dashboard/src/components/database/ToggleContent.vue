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
      class="flex flex-row justify-between items-center gap-2 p-4"
      :class="{ '!pb-2': isVisible }"
    >
      <button
        type="button"
        class="flex-1 text-left select-none"
        :aria-expanded="isVisible"
        @click="isVisible = !isVisible"
      >
        <p class="font-medium text-ink-gray-8">{{ label }}</p>
        <p v-if="subLabel" class="mt-2 text-ink-gray-7 text-sm">{{ subLabel }}</p>
      </button>

      <slot v-if="isVisible" name="actions" />
    </div>

    <!-- A 0fr/1fr grid row animates to the content's own height, which a
         height transition cannot do without measuring it first. -->
    <div
      class="grid duration-200 transition-[grid-template-rows] ease-[var(--ease-out)]"
      :class="isVisible ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
    >
      <div class="overflow-hidden" :inert="!isVisible">
        <div class="text-sm leading-normal">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>
