<template>
  <div class="gap-4 grid grid-cols-1 sm:grid-cols-2">
    <SiteUptime :site-name="siteName" :window="window" />

    <template v-if="loading">
      <Skeleton v-for="i in 12" :key="i" class="rounded-6 h-[340px]" />
    </template>
    <ErrorMessage v-else-if="error" :message="error" class="sm:col-span-2" />

    <template v-else>
      <ChartCard v-for="chart in charts" :key="chart.key" :title="chart.title">
        <div
          v-if="!chart.config.series.length"
          class="flex flex-col flex-1 justify-center items-center gap-1 min-h-[300px] text-center"
        >
          <span class="size-6 text-ink-gray-3 lucide-chart-bar" />
          <p class="font-medium text-ink-gray-7 text-xs">No usage yet</p>
          <p class="text-ink-gray-5 text-xs">Data will appear here once activity is tracked</p>
        </div>
        <AxisChart
          v-else
          :config="chart.config"
          class="w-full min-w-0 h-full min-h-[300px] px-2 sm:px-4 pb-2"
        />
      </ChartCard>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ErrorMessage, Skeleton } from 'frappe-ui'
import { AxisChart } from 'frappe-ui/experimental'
import ChartCard from '@/components/common/ChartCard.vue'
import SiteUptime from '@/components/dashboard/SiteUptime.vue'
import { apiErrorMessage } from '@/api/client'
import { sitesApi } from '@/api/sites'

const props = defineProps({
  siteName: { type: String, required: true },
  window: { type: String, default: '24h' },
})

const TIME_GRAIN = {
  '30m': 'minute',
  '1h': 'minute',
  '6h': 'hour',
  '12h': 'hour',
  '24h': 'hour',
  '1w': 'day',
}

const loading = ref(true)
const error = ref('')
const data = ref(null)

const GRID = { show: true, lineStyle: { type: 'dashed', color: 'var(--outline-gray-2)' } }
const PALETTE = ['#10b981', '#ef4444', '#2490ef', '#f59e0b', '#8b5cf6']

const numberFormat = new Intl.NumberFormat()
const dateFormat = {
  month: 'long',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
}

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
// Series names come from logged request paths/job methods/IPs - attacker-controlled
// data that ends up here as an HTML string, so it must be escaped before interpolation.
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c])

// Custom tooltip: lets the label wrap without breaking the number, and reuses
// ECharts' own marker HTML so the dot color always matches the bar/legend.
function tooltipFormatter(paramsInput) {
  const params = (Array.isArray(paramsInput) ? paramsInput : [paramsInput]).filter(
    (p) => p.value?.[1],
  )
  if (!params.length) return ''
  const rows = params
    .slice()
    .sort((a, b) => b.value[1] - a.value[1])
    .map(
      (p) => `
      <div class="flex items-start gap-2 py-0.5" style="display:flex;white-space:normal;">
        ${p.marker}
        <span class="flex-1 min-w-0" style="flex:1 1 auto;min-width:0;overflow-wrap:break-word;white-space:normal;">${escapeHtml(p.seriesName)}</span>
        <span class="font-bold shrink-0" style="flex:0 0 auto;white-space:nowrap;">${numberFormat.format(p.value[1])}</span>
      </div>
    `,
    )
    .join('')
  const date = new Date(params[0].value[0]).toLocaleString(undefined, dateFormat)
  return `<div style="max-width:420px;white-space:normal;"><div class="mb-1">${date}</div>${rows}</div>`
}

const axisMax = computed(() => data.value?.now ?? Date.now())
const axisMin = computed(() => axisMax.value - (data.value?.window_seconds ?? 0) * 1000)

// series.name must match the data key holding that category's value.
function timelineConfig(timeline, valueLabel, chartType = 'bar') {
  const categories = timeline?.categories ?? []
  return {
    data: timeline?.points ?? [],
    stacked: true,
    xAxis: {
      key: 'time',
      type: 'time',
      timeGrain: TIME_GRAIN[props.window] ?? 'hour',
      echartOptions: { min: axisMin.value, max: axisMax.value, splitLine: GRID },
    },
    yAxis: { yMin: 0, echartOptions: { name: valueLabel, splitLine: GRID } },
    series: categories.map((name, i) => ({
      name,
      type: chartType,
      color: PALETTE[i % PALETTE.length],
      ...(chartType === 'bar' && { echartOptions: { itemStyle: { borderRadius: 0 } } }),
    })),
    echartOptions: { tooltip: { formatter: tooltipFormatter } },
  }
}

const CHARTS = [
  ['requests_over_time', 'Requests', 'Requests', 'line'],
  ['top_ips', 'Requests by IP', 'Requests'],
  ['background_jobs_over_time', 'Background jobs', 'Runs', 'line'],
  ['top_paths', 'Frequent requests', 'Requests'],
  ['slowest_requests', 'Slowest requests', 'Duration (s)'],
  ['avg_request_duration', 'Individual request time (average)', 'Duration (s)'],
  ['top_jobs', 'Frequent background jobs', 'Runs'],
  ['avg_job_duration', 'Individual background job (average)', 'Duration (s)'],
  ['frequent_slow_queries', 'Frequent slow queries', 'Count'],
  ['slowest_queries', 'Top slow queries', 'Duration (s)'],
  ['slowest_jobs', 'Slowest background jobs', 'Duration (s)'],
  ['slowest_reports', 'Slowest reports', 'Duration (s)'],
]

const charts = computed(() =>
  CHARTS.map(([key, title, valueLabel, chartType]) => ({
    key,
    title,
    config: timelineConfig(data.value?.[key], valueLabel, chartType),
  })).filter((chart) => chart.key !== 'slowest_reports' || chart.config.series.length),
)

// Rapid window switches can resolve out of order; only the most recently
// started load is allowed to write to state.
let loadGeneration = 0

async function load() {
  const generation = ++loadGeneration
  loading.value = true
  error.value = ''
  try {
    const result = await sitesApi.monitoring.get(props.siteName, props.window)
    if (generation !== loadGeneration) return
    if (result.error) throw new Error(apiErrorMessage(result, 'Could not load monitoring data.'))
    data.value = result
  } catch (e) {
    if (generation !== loadGeneration) return
    error.value = e.message || 'Could not load monitoring data.'
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

watch(() => [props.siteName, props.window], load)
onMounted(load)
</script>
