<script setup lang="ts">
import { computed, ref } from 'vue'
import { Badge, Button, Switch } from 'frappe-ui'

interface Props {
  title: string
  subtitle?: string
  badge?: string | any[]
  loading?: boolean
  showAutoRefresh?: boolean
  autoRefresh?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  subtitle: '',
  badge: '',
  loading: false,
  showAutoRefresh: false,
  autoRefresh: false,
})

defineEmits(['refresh', 'update:autoRefresh'])

const badges = computed(() => [props.badge].flat().filter(Boolean))

const isOpen = ref(false)
</script>

<template>
  <div class="bg-surface-white border rounded-6 border-outline-gray-2">
    <div class="flex justify-between items-start gap-3 p-4">
      <button
        type="button"
        class="flex-1 min-w-0 text-left"
        :aria-expanded="isOpen"
        @click="isOpen = !isOpen"
      >
        <span class="flex flex-wrap items-center gap-2">
          <h3 class="font-semibold text-ink-gray-9 text-base">{{ title }}</h3>
          <Badge v-for="label in badges" :key="label" :label="label" theme="gray" size="sm" />
        </span>

        <p v-if="subtitle" class="mt-0.5 text-ink-gray-5 text-sm">{{ subtitle }}</p>
      </button>

      <div v-if="isOpen" class="flex items-center gap-3 shrink-0">
        <slot name="actions" />
        <label v-if="showAutoRefresh" class="flex items-center gap-2 cursor-pointer">
          <Switch
            size="sm"
            :model-value="autoRefresh"
            @update:model-value="$emit('update:autoRefresh', $event)"
          />
          <span class="text-ink-gray-7 text-sm">Auto Refresh</span>
        </label>

        <Button
          variant="ghost"
          size="sm"
          icon="lucide-refresh-cw"
          tooltip="Refresh"
          aria-label="Refresh"
          :loading="loading"
          @click="$emit('refresh')"
        />
      </div>
    </div>

    <div
      class="grid duration-200 transition-[grid-template-rows] ease-[var(--ease-out)]"
      :class="isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
    >
      <div class="overflow-hidden" :inert="!isOpen">
        <div class="border-t border-outline-gray-2 overflow-x-auto">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>
