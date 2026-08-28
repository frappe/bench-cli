<script setup lang="ts">
import { computed } from 'vue'

import UsageMeter from '@/components/common/UsageMeter.vue'

const props = defineProps({
  size: { type: Object, required: true },
})

const COLORS = { data: 'red-7', index: 'cyan-7', claimable: 'amber-7' }

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
  <UsageMeter :parts="parts" />
</template>
