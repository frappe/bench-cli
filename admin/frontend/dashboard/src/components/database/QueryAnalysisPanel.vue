<script setup lang="ts">
import { Button, ErrorMessage, TabButtons, Tooltip } from 'frappe-ui'
import { computed, ref } from 'vue'

import PerformanceSchemaNotice from '@/components/database/PerformanceSchemaNotice.vue'
import ResultTable from '@/components/database/ResultTable.vue'
import ToggleContent from '@/components/database/ToggleContent.vue'

import { formatCount, formatMilliseconds } from '@/utils/format'

const props = defineProps({
  report: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  // Server-wide, findings span every site, so each row names the site it came from.
  showSite: { type: Boolean, default: false },
  siteByDatabase: { type: Object, default: () => ({}) },
})

defineEmits(['refresh'])

const tab = ref('time')

const enabled = computed(() => Boolean(props.report?.performance_schema_enabled))

// A database whose site is gone from the bench keeps its own name.
const siteLabel = (database) => props.siteByDatabase[database] || database || '—'

const withSite = (columns) => (props.showSite ? ['Site', ...columns] : columns)

const siteCell = (row) => (props.showSite ? [siteLabel(row.database)] : [])

const tabOptions = [
  { label: 'Time consuming', value: 'time' },
  { label: 'Full table scans', value: 'scans' },
]

const tabs = computed(() => [
  {
    value: 'time',
    columns: withSite(['Percentage', 'Calls', 'Avg Time', 'Query']),
    rows: (props.report?.time_consuming_queries ?? []).map((row) => [
      ...siteCell(row),
      row.percent,
      row.calls,
      row.average_time_ms,
      row.query,
    ]),
  },
  {
    value: 'scans',
    columns: withSite(['Rows Examined', 'Rows Sent', 'Calls', 'Query']),
    rows: (props.report?.full_table_scan_queries ?? []).map((row) => [
      ...siteCell(row),
      row.rows_examined,
      row.rows_sent,
      row.calls,
      row.query,
    ]),
  },
])

const activeTab = computed(() => tabs.value.find((entry) => entry.value === tab.value))

const cellFormatters = {
  Percentage: (value) => `${Number(value).toFixed(1)}%`,
  'Rows Examined': formatCount,
  'Rows Sent': formatCount,
  Calls: formatCount,
  'Avg Time': formatMilliseconds,
}

const fullViewFormatters = { Query: (value) => value }

const alignColumns = {
  Percentage: 'right',
  'Rows Examined': 'right',
  'Rows Sent': 'right',
  Calls: 'right',
  'Avg Time': 'right',
}
</script>

<template>
  <ToggleContent
    label="SQL Query Analysis"
    sub-label="Check the concerning queries that might be affecting your database performance"
  >
    <template #actions>
      <Tooltip text="Refresh query analysis">
        <Button
          variant="ghost"
          icon="lucide-refresh-cw"
          :loading="loading"
          aria-label="Refresh query analysis"
          @click="$emit('refresh')"
        />
      </Tooltip>
    </template>

    <ErrorMessage v-if="error" :message="error" class="m-4" />
    <template v-else>
      <div class="px-4 pb-3">
        <TabButtons v-model="tab" :options="tabOptions" size="sm" />
      </div>

      <PerformanceSchemaNotice v-if="!enabled" />
      <ResultTable
        v-else
        :columns="activeTab.columns"
        :rows="activeTab.rows"
        :align="alignColumns"
        :cell-formatters="cellFormatters"
        :full-view-formatters="fullViewFormatters"
        border-less
        is-truncate-text
      />
    </template>
  </ToggleContent>
</template>
