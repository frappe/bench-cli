<script setup lang="ts">
import { Button, ErrorMessage, TabButtons, Tooltip } from 'frappe-ui'
import { computed, ref } from 'vue'

import PerformanceSchemaNotice from '@/components/database/PerformanceSchemaNotice.vue'
import ResultTable from '@/components/database/ResultTable.vue'
import ToggleContent from '@/components/database/ToggleContent.vue'

const props = defineProps({
  report: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  showSite: { type: Boolean, default: false },
  siteByDatabase: { type: Object, default: () => ({}) },
})

defineEmits(['refresh'])

const tab = ref('unused')

const enabled = computed(() => Boolean(props.report?.performance_schema_enabled))

const siteLabel = (database) => props.siteByDatabase[database] || database || '—'

const withSite = (columns) => (props.showSite ? ['Site', ...columns] : columns)

const siteCell = (row) => (props.showSite ? [siteLabel(row.database)] : [])

// Redundant indexes come from information_schema, so that tab keeps working
// while Performance Schema is off.
const tabOptions = [
  { label: 'Unused', value: 'unused' },
  { label: 'Redundant', value: 'redundant' },
]

const tabs = computed(() => [
  {
    value: 'unused',
    needsPerformanceSchema: true,
    columns: withSite(['Table Name', 'Index Name']),
    rows: (props.report?.unused_indexes ?? []).map((row) => [
      ...siteCell(row),
      row.table,
      row.index,
    ]),
  },
  {
    value: 'redundant',
    needsPerformanceSchema: false,
    columns: withSite([
      'Table Name',
      'Dominant Index',
      'Dominant Index Columns',
      'Redundant Index',
      'Redundant Index Columns',
    ]),
    rows: (props.report?.redundant_indexes ?? []).map((row) => [
      ...siteCell(row),
      row.table,
      row.dominant_index,
      row.dominant_index_columns,
      row.redundant_index,
      row.redundant_index_columns,
    ]),
  },
])

const activeTab = computed(() => tabs.value.find((entry) => entry.value === tab.value))
</script>

<template>
  <ToggleContent label="Database Index Analysis" sub-label="Analyze the indexes of the database">
    <template #actions>
      <Tooltip text="Refresh index analysis">
        <Button
          variant="ghost"
          icon="lucide-refresh-cw"
          :loading="loading"
          aria-label="Refresh index analysis"
          @click="$emit('refresh')"
        />
      </Tooltip>
    </template>

    <ErrorMessage v-if="error" :message="error" class="m-4" />
    <template v-else>
      <div class="px-4 pb-3">
        <TabButtons v-model="tab" :options="tabOptions" size="sm" />
      </div>

      <PerformanceSchemaNotice v-if="activeTab.needsPerformanceSchema && !enabled" />
      <ResultTable
        v-else
        :columns="activeTab.columns"
        :rows="activeTab.rows"
        border-less
        is-truncate-text
      />
    </template>
  </ToggleContent>
</template>
