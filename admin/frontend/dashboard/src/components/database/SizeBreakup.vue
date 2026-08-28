<script setup lang="ts">
import { computed } from 'vue'

import UsageMeter from '@/components/common/UsageMeter.vue'

const props = defineProps({
  size: { type: Object, required: true },
})

// Data and index are both space in use, so they share one hue at two
// strengths; claimable is warm to set apart the space a rebuild gives back.
const COLORS = { data: 'blue-7', index: 'blue-4', claimable: 'amber-5' }

// Segments are shares of what the database holds. Free disk space belongs to
// the Storage page, which reports it against the whole volume.
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
