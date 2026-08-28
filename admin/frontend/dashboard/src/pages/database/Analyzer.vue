<script setup lang="ts">
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingText,
  Switch,
  Tooltip,
  toast,
} from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import IndexAnalysisPanel from '@/components/database/IndexAnalysisPanel.vue'
import QueryAnalysisPanel from '@/components/database/QueryAnalysisPanel.vue'
import ResultTable from '@/components/database/ResultTable.vue'
import SizeBreakup from '@/components/database/SizeBreakup.vue'
import TableSizesDialog from '@/components/database/TableSizesDialog.vue'
import ToggleContent from '@/components/database/ToggleContent.vue'

import { apiErrorMessage } from '@/api/client'
import { databaseApi } from '@/api/database'
import { formatBytes } from '@/utils/format'
import { relativeTime } from '@/utils/taskFormat'

const AUTO_REFRESH_INTERVAL_MS = 2000

const processColumns = ['ID', 'State', 'Time', 'User', 'Host', 'Command', 'Query']
const processAlign = { Time: 'right' }

const lockColumns = [
  'ID',
  'Type',
  'Mode',
  'Table',
  'Index',
  'State',
  'Started',
  'Query',
  'Rows Locked',
  'Rows Modified',
]
const lockAlign = { 'Rows Locked': 'right', 'Rows Modified': 'right' }

const binlogColumns = ['File', 'Date', 'Size']
const binlogAlign = { Size: 'right' }

const durationFormatters = { Time: (value) => (value === null ? '—' : `${Math.round(value)}s`) }
const queryFullView = { Query: (value) => value }

const route = useRoute()

const loading = ref(false)
const error = ref('')
const diagnostics = ref(null)
const configuredEngine = ref('')
const sites = ref([])
const selectedSite = ref('')

const processes = ref([])
const processesLoading = ref(false)
const processesError = ref('')

const lockWaits = ref([])
const lockWaitsLoading = ref(false)
const lockWaitsError = ref('')
const autoRefreshLocks = ref(true)
let lockWaitsTimer = null
let lockWaitsPollVersion = 0
let lockWaitsRequest = null
let lockWaitsRequestSite = null
let lockWaitsReloadQueued = false

const binlogs = ref([])
const binlogsLoading = ref(false)
const binlogsError = ref('')

const size = ref(null)
const sizeLoading = ref(false)
const sizeError = ref('')
const showTableSizes = ref(false)

const performance = ref(null)
const performanceLoading = ref(false)
const performanceError = ref('')

const killTarget = ref(null)
const showKillDialog = ref(false)
const killing = ref(false)
const killError = ref('')

const showPurgeDialog = ref(false)
const pendingIndex = ref(-1)
const purging = ref(false)
const purgeError = ref('')

const processRows = computed(() =>
  processes.value.map((process) => [
    process.id,
    process.state || '—',
    process.duration_seconds,
    process.user || '—',
    process.host || '—',
    process.command || '—',
    process.query || '—',
  ]),
)

const lockRows = computed(() =>
  lockWaits.value.map((row) => [
    row.id,
    row.type,
    row.mode,
    row.table || '—',
    row.index || '—',
    row.state || '—',
    row.started || '—',
    row.query || '—',
    row.rows_locked ?? '—',
    row.rows_modified ?? '—',
  ]),
)

const binlogRows = computed(() =>
  binlogs.value.map((file) => [file.name, fileAge(file), formatBytes(file.size_bytes)]),
)

const killDetails = computed(() => {
  const process = killTarget.value
  if (!process) return []
  return [
    { label: 'User', value: process.user || '—' },
    { label: 'Database', value: process.database || '—' },
    { label: 'State', value: process.command || '—' },
    { label: 'Running for', value: formatSeconds(process.duration_seconds) },
  ]
})

const killQuery = computed(() => killTarget.value?.query || '')

const pendingFiles = computed(() =>
  pendingIndex.value < 0 ? [] : binlogs.value.slice(0, pendingIndex.value + 1),
)
const pendingSize = computed(() =>
  formatBytes(pendingFiles.value.reduce((total, file) => total + file.size_bytes, 0)),
)

// Deletion is always a contiguous run from the oldest file, so the range says
// everything a list of names would - and stays readable at hundreds of files.
const purgeDetails = computed(() => {
  const files = pendingFiles.value
  if (!files.length) return []
  const kept = binlogs.value[pendingIndex.value + 1]
  return [
    { label: 'Oldest deleted', value: files[0].name },
    { label: 'Newest deleted', value: files[files.length - 1].name },
    { label: 'Kept from', value: kept ? kept.name : '—' },
  ]
})

// Binary logs are a MariaDB concept; the engine reports no status when it has none.
const hasBinlogs = computed(() => Boolean(diagnostics.value?.binlog))

// Only sites on this server can be scoped to; a SQLite site owns a file, not a
// database on the bench's engine.
const siteOptions = computed(() => [
  { label: 'All databases', value: '' },
  ...sites.value
    .filter((site) => site.db_type === configuredEngine.value)
    .map((site) => ({ label: site.name, value: site.name })),
])

// Server-wide findings carry a hashed database name; the site that owns it is
// what an operator actually recognises. Databases with no site keep their name.
const siteByDatabase = computed(() =>
  Object.fromEntries(
    sites.value.filter((site) => site.db_name).map((site) => [site.db_name, site.name]),
  ),
)

const formatSeconds = (seconds) => (seconds == null ? '—' : `${Math.round(seconds)}s`)

const fileAge = (file) =>
  file.modified_ms ? relativeTime(new Date(file.modified_ms).toISOString()) : '—'

const confirmKill = (process) => {
  killTarget.value = process
  killError.value = ''
  showKillDialog.value = true
}

const kill = async () => {
  killing.value = true
  killError.value = ''
  try {
    const result = await databaseApi.killProcess(killTarget.value.id)
    if (result.error) throw new Error(apiErrorMessage(result, 'Could not kill the process.'))
    showKillDialog.value = false
    toast.success(`Killed process ${killTarget.value.id}`)
    await loadProcesses()
  } catch (e) {
    killError.value = e.message || 'Could not kill the process.'
  } finally {
    killing.value = false
  }
}

const confirmPurge = (index) => {
  pendingIndex.value = index
  purgeError.value = ''
  showPurgeDialog.value = true
}

const purge = async () => {
  // PURGE keeps the named file, so target the one just after the last selected.
  const keepFrom = binlogs.value[pendingIndex.value + 1]
  if (!keepFrom) return
  purging.value = true
  purgeError.value = ''
  try {
    const result = await databaseApi.binlogs.purge(keepFrom.name)
    if (result.error) throw new Error(apiErrorMessage(result, 'Could not delete binary logs.'))
    showPurgeDialog.value = false
    toast.success('Binary logs deleted')
    await loadBinlogs()
  } catch (e) {
    purgeError.value = e.message || 'Could not delete binary logs.'
  } finally {
    purging.value = false
  }
}

const loadProcesses = async () => {
  processesLoading.value = true
  processesError.value = ''
  try {
    const result = await databaseApi.processList(selectedSite.value)
    if (result?.error)
      throw new Error(apiErrorMessage(result, 'Could not load database processes.'))
    processes.value = Array.isArray(result) ? result : []
  } catch (e) {
    processesError.value = e.message || 'Could not load database processes.'
  } finally {
    processesLoading.value = false
  }
}

const loadLockWaits = () => {
  if (lockWaitsRequest) {
    if (lockWaitsRequestSite !== selectedSite.value) lockWaitsReloadQueued = true
    return lockWaitsRequest
  }
  lockWaitsRequest = drainLockWaitsRequests()
  return lockWaitsRequest
}

const drainLockWaitsRequests = async () => {
  lockWaitsLoading.value = true
  try {
    do {
      lockWaitsReloadQueued = false
      await fetchLockWaits()
    } while (lockWaitsReloadQueued)
  } finally {
    lockWaitsLoading.value = false
    lockWaitsRequest = null
    lockWaitsRequestSite = null
  }
}

const fetchLockWaits = async () => {
  const site = selectedSite.value
  lockWaitsRequestSite = site
  lockWaitsError.value = ''
  try {
    const result = await databaseApi.lockWaitRows(site)
    if (site !== selectedSite.value) {
      lockWaitsReloadQueued = true
      return
    }
    if (result?.error)
      throw new Error(apiErrorMessage(result, 'Could not load database lock waits.'))
    lockWaits.value = Array.isArray(result) ? result : []
  } catch (e) {
    if (site !== selectedSite.value) lockWaitsReloadQueued = true
    else lockWaitsError.value = e.message || 'Could not load database lock waits.'
  }
}

const loadSize = async () => {
  sizeLoading.value = true
  sizeError.value = ''
  try {
    const result = await databaseApi.size(selectedSite.value)
    if (result?.error) throw new Error(apiErrorMessage(result, 'Could not read the database size.'))
    size.value = result
  } catch (e) {
    size.value = null
    sizeError.value = e.message || 'Could not read the database size.'
  } finally {
    sizeLoading.value = false
  }
}

const loadPerformance = async () => {
  performanceLoading.value = true
  performanceError.value = ''
  try {
    const result = await databaseApi.performanceReport(selectedSite.value)
    if (result?.error)
      throw new Error(apiErrorMessage(result, 'Could not read the performance report.'))
    performance.value = result
  } catch (e) {
    performance.value = null
    performanceError.value = e.message || 'Could not read the performance report.'
  } finally {
    performanceLoading.value = false
  }
}

const loadBinlogs = async () => {
  binlogsLoading.value = true
  binlogsError.value = ''
  try {
    const result = await databaseApi.binlogs.list()
    if (result?.error) throw new Error(apiErrorMessage(result, 'Could not load binary logs.'))
    binlogs.value = Array.isArray(result) ? result : []
  } catch (e) {
    binlogsError.value = e.message || 'Could not load binary logs.'
  } finally {
    binlogsLoading.value = false
  }
}

const pollLockWaits = async (version) => {
  await loadLockWaits()
  if (version !== lockWaitsPollVersion || !autoRefreshLocks.value) return
  lockWaitsTimer = setTimeout(() => pollLockWaits(version), AUTO_REFRESH_INTERVAL_MS)
}

const startLockWaitsAutoRefresh = () => {
  stopLockWaitsAutoRefresh()
  const version = lockWaitsPollVersion
  lockWaitsTimer = setTimeout(() => pollLockWaits(version), AUTO_REFRESH_INTERVAL_MS)
}

const stopLockWaitsAutoRefresh = () => {
  lockWaitsPollVersion += 1
  if (lockWaitsTimer) clearTimeout(lockWaitsTimer)
  lockWaitsTimer = null
}

watch(autoRefreshLocks, (enabled) => {
  if (enabled) startLockWaitsAutoRefresh()
  else stopLockWaitsAutoRefresh()
})

// Binary logs are server-wide, so only the scoped panels refetch.
watch(selectedSite, () => {
  loadProcesses()
  loadLockWaits()
  loadSize()
  loadPerformance()
})

onUnmounted(stopLockWaitsAutoRefresh)

const loadSites = async () => {
  try {
    const result = await databaseApi.sites()
    sites.value = Array.isArray(result) ? result : []
  } catch {
    sites.value = [] // Scoping is optional - the page still works server-wide.
  }
}

const load = async () => {
  loading.value = true
  error.value = ''
  if (route.query.site) selectedSite.value = String(route.query.site)
  try {
    const result = await databaseApi.diagnostics()
    if (result.error)
      throw new Error(apiErrorMessage(result, 'Could not load database diagnostics.'))
    diagnostics.value = result
    configuredEngine.value = result.engine
    if (!result.supported) return
    const panels = [loadSites(), loadSize(), loadProcesses(), loadLockWaits(), loadPerformance()]
    if (hasBinlogs.value) panels.push(loadBinlogs())
    await Promise.all(panels)
    if (autoRefreshLocks.value) startLockWaitsAutoRefresh()
  } catch (e) {
    error.value = e.message || 'Could not load database diagnostics.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <Teleport defer to="#header-actions">
    <FormControl
      v-if="siteOptions.length > 1"
      type="select"
      v-model="selectedSite"
      :options="siteOptions"
      class="w-32 sm:w-44"
    />
  </Teleport>

  <div v-if="loading && !diagnostics" class="flex justify-center py-16">
    <LoadingText />
  </div>

  <div
    v-else-if="diagnostics && !diagnostics.supported"
    class="flex flex-col items-center gap-1 bg-surface-white py-14 border rounded-6 border-outline-gray-2 text-center"
  >
    <span class="size-6 text-ink-gray-3 lucide-database" />
    <p class="font-medium text-ink-gray-7 text-sm">No database server</p>
    <p class="max-w-sm text-ink-gray-5 text-xs">{{ diagnostics.reason }}</p>
  </div>

  <ErrorMessage v-else-if="error" :message="error" />

  <div v-else-if="diagnostics" class="flex flex-col mt-2">
    <!-- Database Size Breakup -->
    <div>
      <div class="flex flex-row justify-between items-center">
        <p class="font-medium text-ink-gray-8 text-base">Database Size Breakup</p>
        <div class="flex flex-row gap-2">
          <Button v-if="selectedSite" @click="showTableSizes = true">View Details</Button>
          <Tooltip text="Refresh database size">
            <Button
              variant="ghost"
              icon="lucide-refresh-cw"
              :loading="sizeLoading"
              aria-label="Refresh database size"
              @click="loadSize"
            />
          </Tooltip>
        </div>
      </div>

      <ErrorMessage v-if="sizeError" :message="sizeError" class="mt-4" />
      <div v-else-if="size" class="mt-4">
        <SizeBreakup :size="size" />
      </div>
    </div>

    <!-- Database Processes -->
    <ToggleContent
      class="mt-3"
      label="Database Processes"
      sub-label="Analyze the processes of the database"
    >
      <template #actions>
        <Tooltip text="Refresh processes">
          <Button
            variant="ghost"
            icon="lucide-refresh-cw"
            :loading="processesLoading"
            aria-label="Refresh processes"
            @click="loadProcesses"
          />
        </Tooltip>
      </template>

      <ErrorMessage v-if="processesError" :message="processesError" class="m-4" />
      <ResultTable
        v-else
        class="mt-2"
        :columns="processColumns"
        :rows="processRows"
        :align="processAlign"
        :cell-formatters="durationFormatters"
        :full-view-formatters="queryFullView"
        action-header-label="Kill"
        border-less
        is-truncate-text
      >
        <template #action="{ index }">
          <Button variant="ghost" theme="red" icon-left="x" @click="confirmKill(processes[index])">
            Kill
          </Button>
        </template>
      </ResultTable>
    </ToggleContent>

    <!-- Database Locks -->
    <ToggleContent
      class="mt-3"
      label="Database Locks"
      sub-label="Analyze the lock waits of the database"
    >
      <template #actions>
        <div class="flex flex-row items-center gap-4">
          <div class="flex flex-row items-center gap-2">
            <Switch v-model="autoRefreshLocks" />
            <p class="text-ink-gray-7 text-base">Auto Refresh</p>
          </div>
          <Tooltip text="Refresh lock waits">
            <Button
              variant="ghost"
              icon="lucide-refresh-cw"
              :loading="lockWaitsLoading"
              aria-label="Refresh lock waits"
              @click="loadLockWaits"
            />
          </Tooltip>
        </div>
      </template>

      <ErrorMessage v-if="lockWaitsError" :message="lockWaitsError" class="m-4" />
      <ResultTable
        v-else
        class="mt-2"
        :columns="lockColumns"
        :rows="lockRows"
        :align="lockAlign"
        :full-view-formatters="queryFullView"
        border-less
        is-truncate-text
      />
    </ToggleContent>

    <QueryAnalysisPanel
      class="mt-3"
      :report="performance"
      :loading="performanceLoading"
      :error="performanceError"
      :show-site="!selectedSite"
      :site-by-database="siteByDatabase"
      @refresh="loadPerformance"
    />

    <IndexAnalysisPanel
      class="mt-3"
      :report="performance"
      :loading="performanceLoading"
      :error="performanceError"
      :show-site="!selectedSite"
      :site-by-database="siteByDatabase"
      @refresh="loadPerformance"
    />

    <!-- Database Binary Logs -->
    <ToggleContent
      v-if="hasBinlogs"
      class="mt-3"
      label="Database Binary Logs"
      sub-label="Manage the binary logs of the database. They are shared by every bench on this server."
    >
      <template #actions>
        <Tooltip text="Refresh binary logs">
          <Button
            variant="ghost"
            icon="lucide-refresh-cw"
            :loading="binlogsLoading"
            aria-label="Refresh binary logs"
            @click="loadBinlogs"
          />
        </Tooltip>
      </template>

      <ErrorMessage v-if="binlogsError" :message="binlogsError" class="m-4" />
      <div v-else>
        <ResultTable
          class="mt-2"
          :columns="binlogColumns"
          :rows="binlogRows"
          :align="binlogAlign"
          action-header-label="Delete"
          border-less
        >
          <template #action="{ index }">
            <Tooltip
              v-if="index !== binlogs.length - 1"
              text="Delete this file and every older one"
            >
              <Button variant="ghost" theme="red" icon="trash-2" @click="confirmPurge(index)" />
            </Tooltip>
          </template>
        </ResultTable>

        <p v-if="binlogs.length" class="px-3 pb-3 text-ink-gray-5 text-xs">
          The newest log is in use and cannot be deleted. Deleting a file also deletes every older
          one, because the server can only purge them together.
        </p>
      </div>
    </ToggleContent>
  </div>

  <TableSizesDialog v-model:open="showTableSizes" :site="selectedSite" />

  <Dialog v-model="showKillDialog" title="Kill database process" size="sm">
    <p class="text-ink-gray-7 text-sm">
      Close connection <strong>{{ killTarget?.id }}</strong> and roll back whatever it is running?
      Any bench sharing this server may own it.
    </p>

    <dl class="space-y-1.5 bg-surface-gray-1 mt-3 p-3 rounded-6 text-xs">
      <div
        v-for="item in killDetails"
        :key="item.label"
        class="flex justify-between items-baseline gap-4"
      >
        <dt class="text-ink-gray-5 shrink-0">{{ item.label }}</dt>
        <dd class="font-medium text-ink-gray-8 truncate">{{ item.value }}</dd>
      </div>

      <div v-if="killQuery" class="space-y-1.5 pt-1.5 border-t border-outline-gray-2">
        <dt class="text-ink-gray-5">Query</dt>
        <dd class="max-h-24 overflow-y-auto font-mono font-medium text-ink-gray-8 break-all">
          {{ killQuery }}
        </dd>
      </div>
    </dl>

    <ErrorMessage v-if="killError" :message="killError" class="mt-3" />
    <div class="flex justify-end gap-2 mt-4">
      <Button variant="ghost" @click="showKillDialog = false">Cancel</Button>
      <Button variant="solid" theme="red" :loading="killing" @click="kill">Kill process</Button>
    </div>
  </Dialog>

  <Dialog v-model="showPurgeDialog" title="Delete binary logs" size="sm">
    <p class="text-ink-gray-7 text-sm">
      Permanently delete
      <strong
        >{{ pendingFiles.length }}
        file{{ pendingFiles.length === 1 ? '' : 's' }}</strong
      >, freeing {{ pendingSize }}? Binary logs are shared by every bench on this server and are
      used for point-in-time recovery and replication.
    </p>

    <dl class="space-y-1.5 bg-surface-gray-1 mt-3 p-3 rounded-6 text-xs">
      <div
        v-for="item in purgeDetails"
        :key="item.label"
        class="flex justify-between items-baseline gap-4"
      >
        <dt class="text-ink-gray-5 shrink-0">{{ item.label }}</dt>
        <dd class="font-mono font-medium text-ink-gray-8 truncate">{{ item.value }}</dd>
      </div>
    </dl>

    <ErrorMessage v-if="purgeError" :message="purgeError" class="mt-3" />
    <div class="flex justify-end gap-2 mt-4">
      <Button variant="ghost" @click="showPurgeDialog = false">Cancel</Button>
      <Button variant="solid" theme="red" :loading="purging" @click="purge">Delete</Button>
    </div>
  </Dialog>
</template>

<style scoped>
/* A `1fr` grid track takes its minimum from the item's min-content width, so a
   long header label or query would widen the table past the panel and add a
   horizontal scrollbar. Letting the cells shrink keeps every column in view. */
:deep(.grid) > * {
  min-width: 0;
  overflow: hidden;
}
</style>
