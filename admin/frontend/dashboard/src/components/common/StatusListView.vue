<template>
  <!-- ListRow's own hover paints surface-sidebar, transparent in the dark
       theme. Rows are links, hence the descendant selector. -->
  <ListView
    class="[&_a:hover]:bg-surface-gray-1"
    :columns="columns"
    :rows="rows"
    row-key="id"
    :options="{ selectable: false, showTooltip: true, getRowRoute }"
  >
    <template #cell="{ column, row, item }">
      <!-- Keyed on the column, not on the badge: a row without one still has to
           reach this branch, or it falls through to ListRowItem and renders a
           null. Hidden rather than dropped for the same reason. -->
      <Badge
        v-if="column.key === 'badge'"
        v-show="row.badge"
        :label="row.badge?.label"
        :theme="row.badge?.theme"
        variant="subtle"
      />
      <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
    </template>
  </ListView>
</template>

<script setup>
import { Badge } from 'frappe-ui'
import { ListRowItem, ListView } from 'frappe-ui/experimental'

/**
 * A ListView whose `badge` column renders a Badge and whose other columns
 * render as text. Rows need an `id` and, where the badge shows, a `badge` of
 * `{ label, theme }` or null.
 */
defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  getRowRoute: { type: Function, required: true },
})
</script>
