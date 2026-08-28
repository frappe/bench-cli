<script setup lang="ts">
import { Button, Dialog } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  align: { type: Object, default: () => ({}) },
  cellFormatters: { type: Object, default: () => ({}) },
  fullViewFormatters: { type: Object, default: () => ({}) },
  borderLess: { type: Boolean, default: false },
  actionHeaderLabel: { type: String, default: '' },
  isTruncateText: { type: Boolean, default: false },
  truncateLength: { type: Number, default: 70 },
  hideIndexColumn: { type: Boolean, default: false },
  emptyText: { type: String, default: 'No results to display' },
})

const PAGE_SIZE = 10

const page = ref(1)

watch(
  () => props.rows.length,
  () => {
    page.value = Math.min(page.value, pageCount.value)
  },
)

const pageCount = computed(() => Math.max(Math.ceil(props.rows.length / PAGE_SIZE), 1))
const showPagination = computed(() => props.rows.length > PAGE_SIZE)
const pageRows = computed(() =>
  showPagination.value
    ? props.rows.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
    : props.rows,
)
const pageStart = computed(() => (showPagination.value ? (page.value - 1) * PAGE_SIZE + 1 : 1))
const pageEnd = computed(() => pageStart.value + pageRows.value.length - 1)

const isLastRow = (rowIndex) => rowIndex === pageRows.value.length - 1

const rawValue = (row, columnIndex) => row[columnIndex]

const isTruncated = (row, columnIndex) => {
  const value = rawValue(row, columnIndex)
  return props.isTruncateText && typeof value === 'string' && value.length > props.truncateLength
}

const cellText = (row, columnIndex) => {
  const value = rawValue(row, columnIndex)
  if (isTruncated(row, columnIndex)) return value.substring(0, props.truncateLength)
  const formatter = props.cellFormatters[props.columns[columnIndex]]
  return formatter ? formatter(value) : value
}

const showFullView = ref(false)
const fullViewHeader = ref('')
const fullViewBody = ref('')

const openFullView = (row, columnIndex) => {
  const column = props.columns[columnIndex]
  const formatter = props.fullViewFormatters[column]
  const value = rawValue(row, columnIndex)
  fullViewHeader.value = column
  fullViewBody.value = formatter ? formatter(value) : value
  showFullView.value = true
}
</script>

<template>
  <Dialog v-model="showFullView" :title="fullViewHeader" size="2xl">
    <pre
      class="bg-surface-gray-2 mt-2 p-3 border-2 border-outline-gray-1 rounded-6 text-ink-gray-7 text-sm whitespace-pre-wrap"
      >{{ fullViewBody }}</pre
    >
  </Dialog>

  <div
    class="flex flex-col w-full h-full overflow-hidden"
    :class="{ 'border rounded-4': !borderLess }"
  >
    <div class="relative flex flex-col flex-1 overflow-auto text-base">
      <table v-if="columns.length || rows.length" class="border-separate border-spacing-0">
        <thead class="top-0 z-10 sticky bg-surface-gray-1">
          <tr>
            <td v-if="!hideIndexColumn" width="6rem" class="border-b border-r text-ink-gray-8">
              <div class="flex items-center gap-2 px-3 py-2 truncate">#</div>
            </td>
            <td
              v-for="(column, columnIndex) in columns"
              :key="column"
              class="border-b text-ink-gray-8"
              :class="{ 'border-r': columnIndex !== columns.length - 1 || actionHeaderLabel }"
            >
              <div class="flex items-center gap-2 px-3 py-2 truncate">{{ column }}</div>
            </td>
            <td
              v-if="actionHeaderLabel"
              class="border-b border-r w-[10rem] text-ink-gray-8 text-center"
            >
              {{ actionHeaderLabel }}
            </td>
          </tr>
        </thead>

        <tbody>
          <tr v-for="(row, rowIndex) in pageRows" :key="rowIndex">
            <td
              v-if="!hideIndexColumn"
              class="px-3 py-2 border-r truncate"
              :class="{ 'border-b': !(isLastRow(rowIndex) && borderLess) }"
            >
              {{ pageStart + rowIndex }}
            </td>
            <td
              v-for="(column, columnIndex) in columns"
              :key="column"
              :align="align[column] || 'left'"
              class="px-3 py-2 min-w-[6rem] truncate"
              :class="{
                'border-b': !(isLastRow(rowIndex) && borderLess),
                'border-r': columnIndex !== columns.length - 1 || Boolean($slots.action),
              }"
            >
              {{ cellText(row, columnIndex) }}
              <span
                v-if="isTruncated(row, columnIndex)"
                class="inline-block !my-0 ml-2 !w-4 !h-4 text-ink-gray-7 cursor-pointer lucide-maximize-2"
                @click="openFullView(row, columnIndex)"
              />
            </td>
            <td v-if="$slots.action" class="border-b border-r w-[6rem] text-ink-gray-8 text-center">
              <slot name="action" :row="row" :index="pageStart + rowIndex - 1" />
            </td>
          </tr>
          <tr height="99%" class="border-b"></tr>
        </tbody>
      </table>

      <div v-if="!rows.length" class="flex justify-center items-center min-h-[20vh]">
        <div>{{ emptyText }}</div>
      </div>
    </div>

    <div v-if="showPagination" class="flex justify-end items-center gap-3 p-1">
      <p class="text-ink-gray-6 text-sm tnum">
        {{ pageStart }} - {{ pageEnd }} of {{ rows.length }} rows
      </p>
      <div class="flex gap-2">
        <Button variant="ghost" iconLeft="arrow-left" :disabled="page === 1" @click="page--">
          Prev
        </Button>
        <Button
          variant="ghost"
          iconRight="arrow-right"
          :disabled="page >= pageCount"
          @click="page++"
        >
          Next
        </Button>
      </div>
    </div>
  </div>
</template>
