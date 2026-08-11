<script setup lang="ts" generic="Row extends Record<string, any>">
import type { Component } from 'vue'
import Scrollbar from '@/components/common/Scrollbar.vue'

interface Column {
  key: string
  label: string
  class?: string
  component?: Component
}

interface Props {
  columns: Column[]
  rows: Row[]
  height?: string
}

defineProps<Props>()

defineSlots<{
  [key: string]: (props: { row: Row; index: number }) => any
}>()
</script>

<template>
  <Scrollbar class="min-h-0" :class="height || 'flex-1'">
    <table class="border-separate border-spacing-0 min-w-full text-left">
      <thead class="top-0 z-10 sticky">
        <tr>
          <th
            v-for="(column, i) in columns"
            :key="column.key"
            class="bg-surface-gray-2 px-3 py-2 font-normal text-ink-gray-5 text-sm whitespace-nowrap"
            :class="[column.class, i === 0 && 'rounded-l-4', i === columns.length - 1 && 'rounded-r-4']"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>

      <tbody>
        <tr v-for="(row, index) in rows" :key="row.id ?? index">
          <td
            v-for="column in columns"
            :key="column.key"
            class="px-4 py-3 whitespace-nowrap"
            :class="[column.class, index < rows.length - 1 && 'border-b border-outline-gray-1']"
          >
            <slot v-if="$slots[column.key]" :name="column.key" :row="row" :index="index" />
            <component :is="column.component" v-else-if="column.component" :row="row" />
            <template v-else>{{ row[column.key] }}</template>
          </td>
        </tr>
      </tbody>
    </table>
  </Scrollbar>
</template>
