<script setup lang="ts">
import { computed } from 'vue'
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
</script>

<template>
  <div class="bg-surface-white border rounded-6 border-outline-gray-2">
    <div class="flex justify-between items-start gap-3 p-4">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="font-semibold">{{ title }}</h3>
          <Badge v-for="label in badges" :key="label" :label="label" size="sm" />
        </div>

        <p v-if="subtitle" class="mt-0.5 text-ink-gray-5 text-sm">{{ subtitle }}</p>
      </div>

      <div class="flex items-center gap-3 shrink-0">
        <slot name="actions" />
        <label v-if="showAutoRefresh" class="flex items-center gap-2 cursor-pointer">
          <Switch
            :model-value="autoRefresh"
            @update:model-value="$emit('update:autoRefresh', $event)"
          />
          <span class="text-ink-gray-7 text-sm">Auto Refresh</span>
        </label>

        <Button
          icon="lucide-refresh-cw"
          label="Refresh"
          tooltip="Refresh"
          :loading="loading"
          @click="$emit('refresh')"
        />
      </div>
    </div>

    <div class="border-t border-outline-gray-2 overflow-x-auto">
      <slot />
    </div>
  </div>
</template>
