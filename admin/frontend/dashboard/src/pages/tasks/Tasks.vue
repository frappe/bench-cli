<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, ErrorMessage, TabButtons } from 'frappe-ui'

import EmptyState from '@/components/common/EmptyState.vue'
import ListRowSkeleton from '@/components/common/ListRowSkeleton.vue'
import StatusListView from '@/components/common/StatusListView.vue'
import StickyToolbar from '@/components/common/StickyToolbar.vue'

import { useIsMobile } from '@/composables/common/useIsMobile'
import { useTasks } from '@/composables/tasks/useTasks'

import {
  commandLabel,
  siteLabel,
  statusConfig,
  TASK_TYPES,
  taskDuration,
  taskLastRun,
  taskType,
} from '@/utils/taskFormat'
import { taskDetailRoute } from '@/utils/taskRoute'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()
const { tasks, loading, error, load } = useTasks()

const filterOptions = [
  { label: 'All', value: 'all' },
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Failed', value: 'failed' },
  { label: 'Succeeded', value: 'success' },
]
const STATUS_VALUES = filterOptions.map((option) => option.value)

// All three filters live in the URL so filtered views are shareable.
const statusFilter = computed(() => {
  const value = typeof route.query.status === 'string' ? route.query.status : 'all'
  return STATUS_VALUES.includes(value) ? value : 'all'
})
const siteFilter = computed(() => (typeof route.query.site === 'string' ? route.query.site : ''))
const typeFilter = computed(() => (typeof route.query.type === 'string' ? route.query.type : ''))

const visibleTasks = computed(() =>
  tasks.value.filter(
    (task) =>
      (!siteFilter.value || siteLabel(task) === siteFilter.value) &&
      (!typeFilter.value || taskType(task) === typeFilter.value),
  ),
)

// Numeric widths are fr units (ListView convention) so the columns stretch to
// fill the row instead of leaving dead space.
const columns = [
  { label: 'Task', key: 'title', align: 'left', width: 2 },
  { label: 'Site', key: 'site', align: 'left', width: 2 },
  { label: 'Status', key: 'badge', align: 'left', width: 1.5 },
  { label: 'Duration', key: 'duration', align: 'left', width: 1 },
  { label: 'Last run', key: 'timing', align: 'right', width: 2 },
]

// ListRowItem reads row[column.key], so each task is flattened to what renders.
const rows = computed(() =>
  visibleTasks.value.map((task) => ({
    id: task.task_id,
    title: commandLabel(task.command),
    site: siteLabel(task),
    badge: statusConfig(task),
    duration: taskDuration(task),
    timing: taskLastRun(task),
  })),
)

const getRowRoute = (row) => taskDetailRoute(row.id)

// "Other" is a fallback for unknown commands; listed only once one exists.
const typeMenu = computed(() => {
  const present = new Set(tasks.value.map(taskType))
  return [
    { label: 'All types', value: '' },
    ...TASK_TYPES.filter(
      ({ value }) => value !== 'other' || present.has('other') || typeFilter.value === 'other',
    ),
  ].map(({ value, label }) => ({ label, onClick: () => onTypeChange(value) }))
})

// Built from the loaded tasks; a site arriving via the URL is kept even
// when nothing matches, so the trigger still names what is filtering.
const siteMenu = computed(() => {
  const sites = new Set(tasks.value.map(siteLabel))
  if (siteFilter.value) sites.add(siteFilter.value)
  return [
    { label: 'All sites', value: '' },
    ...[...sites].sort().map((site) => ({ label: site, value: site })),
  ].map(({ value, label }) => ({ label, onClick: () => onSiteChange(value) }))
})

const typeLabel = computed(
  () => TASK_TYPES.find(({ value }) => value === typeFilter.value)?.label || 'All types',
)
const siteLabelText = computed(() => siteFilter.value || 'All sites')

// Patch, not replace: changing one filter must not clear the other.
const setFilterQuery = (patch) => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  router.replace({ name: 'Tasks', query })
}

const onSiteChange = (site) => setFilterQuery({ site })
const onTypeChange = (type) => setFilterQuery({ type })

// An empty list means something different when a filter is on - saying "no tasks
// yet" there would be a lie.
const isFiltered = computed(
  () => statusFilter.value !== 'all' || Boolean(siteFilter.value) || Boolean(typeFilter.value),
)

const onFilterChange = (value) => {
  setFilterQuery({ status: value === 'all' ? '' : value })
  load(value)
}

onMounted(() => load(statusFilter.value))
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <StickyToolbar class="flex sm:flex-row flex-col sm:items-center gap-2">
      <TabButtons
        class="shrink-0"
        :size="isMobile ? 'md' : 'sm'"
        :options="filterOptions"
        :modelValue="statusFilter"
        @update:modelValue="onFilterChange"
      />
      <div class="flex flex-1 items-center gap-2 min-w-0">
        <Dropdown :options="typeMenu">
          <template #default="{ open }">
            <Button
              variant="subtle"
              :size="isMobile ? 'md' : 'sm'"
              :active="open"
              class="[&>.truncate]:text-left text-base"
            >
              <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
              {{ typeLabel }}
            </Button>
          </template>
        </Dropdown>

        <div class="flex-1 sm:flex-none min-w-0">
          <Dropdown :options="siteMenu">
            <template #default="{ open }">
              <Button
                variant="subtle"
                :size="isMobile ? 'md' : 'sm'"
                :active="open"
                class="[&>.truncate]:flex-1 [&>.truncate]:text-left text-base w-full sm:w-auto min-w-0"
              >
                <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
                {{ siteLabelText }}
              </Button>
            </template>
          </Dropdown>
        </div>

        <Button
          class="ml-auto sm:ml-auto"
          variant="subtle"
          :size="isMobile ? 'md' : 'sm'"
          icon="lucide-refresh-cw"
          label="Refresh"
          tooltip="Refresh"
          :loading="loading"
          @click="load(statusFilter)"
        />
      </div>
    </StickyToolbar>

    <div v-if="loading" class="-mx-3 mt-4">
      <ListRowSkeleton v-for="index in 6" :key="index" :index="index - 1" />
    </div>

    <div v-else-if="error" class="mt-4">
      <ErrorMessage :message="error" />
    </div>

    <StatusListView
      v-else-if="rows.length"
      class="mt-4"
      :columns="columns"
      :rows="rows"
      :get-row-route="getRowRoute"
    />

    <EmptyState
      v-else
      class="mt-8"
      icon="lucide-list-checks"
      :title="isFiltered ? 'No matching tasks' : 'No tasks yet'"
      :description="
        isFiltered
          ? 'No background jobs match the filters you have applied.'
          : 'Background jobs - backups, deploys, migrations and more - appear here as they run.'
      "
    />
  </div>
</template>
