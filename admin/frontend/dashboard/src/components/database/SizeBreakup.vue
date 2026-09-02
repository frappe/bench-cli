<script setup lang="ts">
import { computed } from 'vue'

import UsageMeter from '@/components/common/UsageMeter.vue'

interface Props {
  size: Record<string, any>
}

const props = defineProps<Props>()

const COLORS = { data: 'blue-7', index: 'blue-4', claimable: 'amber-5' }

const parts = computed(() =>
  props.size.data_bytes == null && props.size.index_bytes == null
    ? [{ label: 'Database Size', bytes: props.size.total_bytes, color: COLORS.data }]
    : [
        { label: 'Data Size', bytes: props.size.data_bytes, color: COLORS.data },
        { label: 'Index Size', bytes: props.size.index_bytes, color: COLORS.index },
        {
          label: 'Claimable Space',
          bytes: props.size.claimable_bytes,
          color: COLORS.claimable,
        },
      ],
)
</script>

<template>
  <UsageMeter :parts="parts" bar-height="h-5" />
</template>
