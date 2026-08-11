<template>
  <!-- 5rem = 3rem sticky header + the shell's 2rem vertical page padding -->
  <div class="flex flex-col h-[calc(100dvh-5rem)]">
    <div class="flex flex-1 sm:gap-4 min-h-0 overflow-hidden">
      <!-- Sidebar: log list -->
      <div
        class="md:flex flex-col w-full md:w-64 overflow-hidden shrink-0"
        :class="selectedFile ? 'hidden' : 'flex'"
      >
        <div class="sm:px-2 pt-2 shrink-0">
          <FormControl
            type="text"
            v-model="fileSearch"
            placeholder="Search log files"
            :size="isSinglePane ? 'md' : 'sm'"
          >
            <template #prefix><span class="size-4 text-ink-gray-5 lucide-search" /></template>
          </FormControl>
        </div>
        <div class="flex flex-col flex-1 gap-1 p-1.5 sm:p-2 overflow-y-auto">
          <LoadingText v-if="logsLoading" class="p-2" />
          <ErrorMessage v-else-if="logsError" :message="logsError" class="p-2" />
          <p v-else-if="!filteredLogs.length" class="p-2 text-ink-gray-4 text-sm">
            No log files found.
          </p>
          <button
            v-else
            v-for="log in filteredLogs"
            :key="log.filename"
            class="sm:px-3 py-2.5 rounded-4 w-full text-left transition-colors shrink-0"
            :class="selectedFile === log.filename ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-1'"
            @click="selectedFile = log.filename"
          >
            <div class="flex items-center gap-2">
              <span class="flex-1 font-medium text-ink-gray-8 text-base truncate">
                {{ log.filename }}
              </span>
              <Tooltip v-if="hasErrors(log)" text="Contains errors">
                <span
                  class="bg-surface-red-5 rounded-full size-1.5 shrink-0"
                  role="img"
                  aria-label="Contains errors"
                />
              </Tooltip>
              <span class="text-ink-gray-4 text-xs shrink-0">
                {{ shortRelativeTime(log.last_modified) }}
              </span>
            </div>
            <div class="mt-0.5 text-ink-gray-4 text-p-sm">{{ formatBytes(log.size_bytes) }}</div>
          </button>
        </div>
      </div>

      <!-- Viewer -->
      <div
        class="md:flex flex-col flex-1 min-w-0 overflow-hidden"
        :class="selectedFile ? 'flex' : 'hidden'"
      >
        <!-- Already inside a bordered panel, so no dashed box of its own. -->
        <div v-if="!selectedFile" class="flex flex-1 justify-center items-center">
          <EmptyState
            :bordered="false"
            icon="lucide-scroll-text"
            title="Select a log file"
            :description="`Output from ${benchName}'s services.`"
          />
        </div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-center gap-2 py-2 shrink-0">
            <!-- Mobile-only: back + filename, replacing the standalone filename bar -->
            <div class="md:hidden flex items-center gap-2">
              <Button
                variant="subtle"
                icon="lucide-arrow-left"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Back to logs"
                tooltip="Back to logs"
                @click="selectedFile = ''"
              />
              <span class="flex-1 min-w-0 font-medium text-ink-gray-8 text-lg truncate">
                {{ selectedFile }}
              </span>
            </div>
            <FormControl
              type="text"
              v-model="search"
              placeholder="Search this log"
              :size="isSinglePane ? 'md' : 'sm'"
              class="flex-1 min-w-0"
              @keydown.enter.exact.prevent="gotoMatch(1)"
              @keydown.enter.shift.prevent="gotoMatch(-1)"
            />
            <div
              v-if="search.trim()"
              class="flex items-center gap-1 text-ink-gray-5 text-xs shrink-0"
            >
              <span class="tabular-nums"
                >{{ matchTotal ? activeMatch + 1 : 0 }}/{{ matchTotal }}</span
              >
              <Button
                variant="subtle"
                icon="lucide-chevron-up"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Previous match"
                tooltip="Previous (Shift+Enter)"
                :disabled="!matchTotal"
                @click="gotoMatch(-1)"
              />
              <Button
                variant="subtle"
                icon="lucide-chevron-down"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Next match"
                tooltip="Next (Enter)"
                :disabled="!matchTotal"
                @click="gotoMatch(1)"
              />
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <div class="w-28 sm:w-32 min-w-0 shrink-0">
                <FormControl
                  type="select"
                  v-model="linesCount"
                  :size="isSinglePane ? 'md' : 'sm'"
                  :disabled="liveMode"
                  :options="[
                    { label: '100 lines', value: 100 },
                    { label: '200 lines', value: 200 },
                    { label: '500 lines', value: 500 },
                    { label: '1000 lines', value: 1000 },
                  ]"
                />
              </div>
              <Button
                class="ml-auto sm:ml-0"
                variant="subtle"
                icon="lucide-refresh-cw"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Refresh"
                tooltip="Refresh"
                :loading="contentLoading"
                @click="loadContent"
              />
              <Button
                v-if="!liveMode"
                variant="subtle"
                icon="lucide-radio"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Live tail"
                tooltip="Live tail"
                @click="startLive"
              />
              <Button
                v-else
                variant="subtle"
                theme="red"
                icon="lucide-radio"
                :size="isSinglePane ? 'md' : 'sm'"
                label="Stop live tail"
                tooltip="Stop live tail"
                @click="() => { stopLive(); loadContent() }"
              />
              <a :href="logsApi.downloadUrl(selectedFile)" class="contents">
                <Button
                  variant="subtle"
                  icon="lucide-download"
                  :size="isSinglePane ? 'md' : 'sm'"
                  label="Download"
                  tooltip="Download"
                />
              </a>
            </div>
          </div>

          <!-- Terminal area -->
          <div ref="viewer" class="flex flex-col flex-1 mt-2 sm:mt-0 overflow-hidden">
            <div v-if="contentError" class="p-4 font-mono text-ink-red-6 text-sm">
              Error: {{ contentError }}
            </div>
            <LogView
              v-else
              ref="terminal"
              :lines="visibleLines"
              :streaming="liveMode"
              fill
              wrap
              rows
              rounded
              class="border border-outline-gray-2"
              :empty-text="contentLoading ? 'Loading…' : 'Log file is empty.'"
            />

            <div
              v-if="rawLines.length"
              class="sm:px-4 pt-2 text-ink-gray-4 text-xs shrink-0"
            >
              {{ totalLineCount }} lines in file
              <template v-if="search.trim()">
                · {{ matchTotal }} match{{ matchTotal !== 1 ? 'es' : '' }}</template
              >
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, ErrorMessage, FormControl, LoadingText, Tooltip } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import LogView from '@/components/logs/LogView.vue'
import { logsApi } from '@/api/logs'
import { escapeHtml, processLine } from '@/utils/ansi'
import { formatBytes } from '@/utils/format'
import { useBench } from '@/composables/benches/useBench'
import { useIsMobile } from '@/composables/common/useIsMobile'

const route = useRoute()
const router = useRouter()

const { name: benchName, load: loadBench } = useBench()

function shortRelativeTime(iso) {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function hasErrors(log) {
  return log.filename.endsWith('.error.log') && log.size_bytes > 0
}

// ── Log list ─────────────────────────────────────────────────────────────
const logs = ref([])
const logsLoading = ref(true)
const logsError = ref('')
const fileSearch = ref('')

const filteredLogs = computed(() => {
  const term = fileSearch.value.trim().toLowerCase()
  return term ? logs.value.filter((log) => log.filename.toLowerCase().includes(term)) : logs.value
})

const totalLineCount = computed(
  () =>
    logs.value.find((log) => log.filename === selectedFile.value)?.line_count ??
    rawLines.value.length,
)

async function loadLogs() {
  logsLoading.value = true
  logsError.value = ''
  try {
    // Sort once here (most recently active first) - filteredLogs only needs to filter.
    logs.value = (await logsApi.list()).sort(
      (a, b) => new Date(b.last_modified) - new Date(a.last_modified),
    )
  } catch (caught) {
    logsError.value = caught.message || 'Failed to load logs'
  } finally {
    logsLoading.value = false
  }
}

// ── Viewer ───────────────────────────────────────────────────────────────
const selectedFile = ref(route.query.file || '')
const rawLines = ref([])
const contentLoading = ref(false)
const contentError = ref('')
const search = ref('')
const linesCount = ref(200)
const liveMode = ref(false)
const terminal = ref(null)
const viewer = ref(null)
const activeMatch = ref(0)
const matchTotal = ref(0)
let eventSource = null
let lastTerm = ''

// Matches the `md:` classes that switch the list/viewer layout.
const isSinglePane = useIsMobile(768)

const isSearching = computed(() => search.value.trim().length > 0)

// Re-run ANSI processing per fetch, not per search keystroke.
const processedLines = computed(() => rawLines.value.map(processLine))

const searchPattern = computed(() => {
  const term = search.value.trim()
  return term ? new RegExp(escapeRegExp(escapeHtml(term)), 'gi') : null
})

// Search highlights in place; data-mi tags matches for jumping.
const visibleLines = computed(() => {
  const pattern = searchPattern.value
  return pattern
    ? processedLines.value.map((line) => highlight(line, pattern))
    : processedLines.value
})

watch(visibleLines, () => nextTick(syncMatches))
watch(linesCount, () => loadContent())

function syncMatches() {
  // Skip the DOM scan entirely when there's nothing to highlight - matters
  // most during live tail, where visibleLines otherwise changes every line.
  if (!isSearching.value) {
    matchTotal.value = 0
    activeMatch.value = -1
    return
  }
  const marks = matchEls()
  matchTotal.value = marks.length
  const term = search.value.trim()
  if (term !== lastTerm) {
    lastTerm = term
    activeMatch.value = marks.length ? 0 : -1
    paintMatches(!liveMode.value)
  } else {
    if (activeMatch.value >= marks.length) activeMatch.value = marks.length - 1
    paintMatches(false)
  }
}

function gotoMatch(delta) {
  const marks = matchEls()
  if (!marks.length) return
  activeMatch.value = (activeMatch.value + delta + marks.length) % marks.length
  paintMatches(true)
}

function matchEls() {
  return viewer.value ? [...viewer.value.querySelectorAll('mark[data-mi]')] : []
}

function paintMatches(scroll) {
  matchEls().forEach((el, index) => {
    const active = index === activeMatch.value
    el.classList.toggle('log-match--active', active)
    if (active && scroll) el.scrollIntoView({ block: 'center' })
  })
}

watch(selectedFile, (filename) => {
  router.replace({ path: '/insights/logs', query: filename ? { file: filename } : {} })
  stopLive()
  rawLines.value = []
  search.value = ''
  if (filename) loadContent()
})

async function loadContent() {
  if (!selectedFile.value) return
  contentLoading.value = true
  contentError.value = ''
  try {
    const data = await logsApi.read(selectedFile.value, linesCount.value)
    rawLines.value = data.lines
    if (!isSearching.value) {
      await nextTick()
      terminal.value?.scrollToBottom()
    }
  } catch (caught) {
    contentError.value = caught.message || 'Failed to load log'
  } finally {
    contentLoading.value = false
  }
}

function startLive() {
  liveMode.value = true
  rawLines.value = []
  eventSource = new EventSource(logsApi.streamUrl(selectedFile.value))
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    rawLines.value.push(data.error ? `ERROR: ${data.error}` : data.line)
    if (rawLines.value.length > 2000) rawLines.value.shift()
  }
  eventSource.onerror = () => stopLive()
}

function stopLive() {
  liveMode.value = false
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

// Wrap matches in rendered HTML, touching only text between tags so ANSI
// <span>s stay intact; the pattern is built from an HTML-escaped term.
function highlight(html, pattern) {
  return html.replace(
    /(<[^>]+>)|([^<]+)/g,
    (_, tag, text) =>
      tag ||
      text.replace(pattern, (match) => `<mark data-mi class="log-match">${match}</mark>`),
  )
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

onMounted(async () => {
  loadBench()
  await loadLogs()
  if (selectedFile.value) {
    loadContent()
  } else if (filteredLogs.value.length && !isSinglePane.value) {
    // Desktop shows both panes, so preselect the most recently active log. On
    // mobile (< md) only one pane is visible at a time - leave the list showing instead.
    selectedFile.value = filteredLogs.value[0].filename
  }
})

onUnmounted(() => stopLive())
</script>

<!-- Unscoped: the <mark>s are injected via v-html and never get the scope attribute. -->
<style>
.log-match {
  background: var(--surface-amber-3);
  color: var(--ink-gray-9);
  border-radius: 2px;
  padding: 0 1px;
}
.log-match--active {
  background: var(--surface-amber-5);
  box-shadow: 0 0 0 2px var(--surface-amber-5);
}
</style>
