<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, ErrorMessage, TabButtons } from 'frappe-ui'

import EmptyState from '@/components/common/EmptyState.vue'
import ListRowSkeleton from '@/components/common/ListRowSkeleton.vue'
import StatusListView from '@/components/common/StatusListView.vue'
import StickyToolbar from '@/components/common/StickyToolbar.vue'

import { useIsMobile } from '@/composables/common/useIsMobile'
import { updatesApi } from '@/api/updates'

import {
  matchesUpdateFilter,
  opTitle,
  pendingActionLabel,
  siteNames,
  sitesLabel,
  stateLabel,
  stateTone,
  UPDATE_FILTERS,
} from '@/utils/updateFormat'
import { fmtDuration, relativeTime } from '@/utils/taskFormat'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const operations = ref([])
const loading = ref(false)
const error = ref('')

const FILTER_VALUES = UPDATE_FILTERS.map((option) => option.value)

// In the URL like the tasks list, so a filtered view survives a reload and can
// be pasted to someone else.
const statusFilter = computed(() => {
  const value = typeof route.query.status === 'string' ? route.query.status : 'all'
  return FILTER_VALUES.includes(value) ? value : 'all'
})
const isFiltered = computed(() => statusFilter.value !== 'all')

// Filtered here rather than by the API: its status filter matches a single
// state, and every tab but Completed and Reverted covers several.
const visibleOperations = computed(() =>
  operations.value.filter((op) => matchesUpdateFilter(op, statusFilter.value)),
)

const onFilterChange = (value) => {
  const query = { ...route.query }
  if (value === 'all') delete query.status
  else query.status = value
  router.replace({ name: 'Updates', query })
}

const badge = (op) => {
  if (op.pending_action) return { label: pendingActionLabel(op.pending_action), theme: 'amber' }
  const tone = stateTone(op.state)
  return { label: stateLabel(op.state), theme: tone === 'orange' ? 'amber' : tone }
}

// Numeric widths are fr units (ListView convention) so the columns stretch to
// fill the row instead of leaving dead space.
const columns = [
  { label: 'Update', key: 'title', align: 'left', width: 2 },
  { label: 'Site', key: 'site', align: 'left', width: 2, getTooltip: (row) => row.siteNames },
  { label: 'Status', key: 'badge', align: 'left', width: 1.5 },
  { label: 'Duration', key: 'duration', align: 'left', width: 1 },
  { label: 'Last run', key: 'timing', align: 'right', width: 2 },
]

// ListRowItem reads row[column.key], so the operation is flattened to the four
// strings the columns render.
const rows = computed(() =>
  visibleOperations.value.map((op) => ({
    id: op.id,
    title: opTitle(op),
    site: sitesLabel(op),
    siteNames: siteNames(op),
    badge: badge(op),
    duration: duration(op),
    timing: relativeTime(op.started_at || op.created_at),
  })),
)

const getRowRoute = (row) => ({ name: 'UpdateDetail', params: { operationId: row.id } })

const duration = (op) => {
  if (!op.finished_at || !op.started_at) return ''
  return fmtDuration((new Date(op.finished_at) - new Date(op.started_at)) / 1000)
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [current, history] = await Promise.all([
      updatesApi.current().catch(() => null),
      updatesApi.list({ limit: 50 }),
    ])
    const past = history.data || []
    // Pin the active/unresolved operation at the top (it is also in history).
    operations.value = current ? [current, ...past.filter((op) => op.id !== current.id)] : past
  } catch (e) {
    error.value = e?.message || 'Could not load updates.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <!-- The tabs need a phone's full content width, so Refresh only joins them
         once there is room to spare. -->
    <Teleport v-if="isMobile" defer to="#header-actions">
      <Button
        variant="subtle"
        size="sm"
        :loading="loading"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        @click="load"
      />
    </Teleport>

    <!-- A flex item sizes to the strip's natural width and overflows the screen;
         a block child is held to the content width and fits. -->
    <StickyToolbar :class="isMobile ? '' : 'flex items-center gap-2'">
      <TabButtons
        :size="isMobile ? 'md' : 'sm'"
        :options="UPDATE_FILTERS"
        :modelValue="statusFilter"
        @update:modelValue="onFilterChange"
      />
      <Button
        v-if="!isMobile"
        class="ml-auto"
        variant="subtle"
        size="sm"
        :loading="loading"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        @click="load"
      />
    </StickyToolbar>

    <div v-if="loading && !operations.length" class="-mx-3 mt-4">
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
      icon="lucide-git-pull-request-arrow"
      :title="isFiltered ? 'No matching updates' : 'No updates yet'"
      :description="
        isFiltered
          ? 'No updates are in this state right now.'
          : 'App updates across your sites appear here, with backup and recovery.'
      "
    />
  </div>
</template>
