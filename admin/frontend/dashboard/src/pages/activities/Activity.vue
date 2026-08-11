<template>
  <div class="flex flex-col mx-auto max-w-4xl h-[calc(100vh-5rem)]">
    <div class="flex justify-between items-center gap-3 shrink-0">
      <div>
        <h1 class="font-semibold text-ink-gray-9 text-xl">Activity</h1>
        <p class="mt-1 text-ink-gray-5 text-p-base">
          A trail of actions taken on this bench - logins, backups, app changes and more.
        </p>
      </div>
      <Button
        variant="subtle"
        size="sm"
        :loading="loading"
        icon-left="lucide-refresh-cw"
        @click="reload"
      >
        Refresh
      </Button>
    </div>

    <div class="flex flex-wrap items-center gap-3 mt-4 shrink-0">
      <div class="w-48">
        <FormControl
          type="select"
          v-model="typeFilter"
          :options="activityTypeOptions"
          @update:modelValue="reload"
        />
      </div>
    </div>

    <div
      v-if="siteFilter"
      class="flex items-center gap-2 bg-surface-blue-1 mt-4 px-3 py-2 rounded-4 shrink-0"
    >
      <span class="lucide-filter size-4 text-ink-blue-7 shrink-0" />
      <p class="flex-1 min-w-0 text-p-sm text-ink-blue-8 truncate">
        Activity on <span class="font-semibold">{{ siteFilter }}</span>
      </p>
      <Button variant="ghost" size="sm" icon="lucide-x" @click="clearSiteFilter" />
    </div>

    <div v-if="loading" class="flex flex-1 justify-center items-center">
      <LoadingText />
    </div>
    <div v-else-if="error" class="mt-4">
      <ErrorMessage :message="error" />
    </div>

    <div
      v-else-if="activities.length"
      class="flex flex-col flex-1 border border-outline-gray-2 rounded-4 mt-4 min-h-0 overflow-hidden"
    >
      <div class="flex-1 overflow-y-auto">
        <table class="w-full text-left">
          <thead
            class="top-0 sticky bg-surface-gray-2 text-ink-gray-5 text-xs uppercase tracking-wide"
          >
            <tr>
              <th class="px-4 py-2.5 font-medium">Activity</th>
              <th class="px-4 py-2.5 font-medium">Resource</th>
              <th class="px-4 py-2.5 font-medium">Triggered by</th>
              <th class="px-4 py-2.5 font-medium text-right">Date/time</th>
            </tr>
          </thead>
          <tbody class="divide-outline-gray-1 divide-y">
            <tr
              v-for="(entry, index) in activities"
              :key="`${entry.logged_at}-${index}`"
              class="hover:bg-surface-gray-1 transition-colors"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <span
                    class="place-items-center grid rounded-full size-8 shrink-0"
                    :class="activityTypeMeta(entry).iconBg"
                  >
                    <span class="size-4" :class="activityTypeMeta(entry).icon" />
                  </span>
                  <span class="font-medium text-ink-gray-9 text-sm">{{
                    activityLabel(entry)
                  }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <RouterLink
                  v-if="activityResourceRoute(entry)"
                  :to="activityResourceRoute(entry)"
                  class="text-ink-gray-7 text-sm no-underline hover:text-ink-gray-9 hover:underline"
                >
                  {{ activityResourceLabel(entry) }}
                </RouterLink>
                <span v-else class="text-ink-gray-3 text-sm">-</span>
              </td>
              <td class="px-4 py-3 text-ink-gray-6 text-sm truncate max-w-[12rem]">
                {{ activityActorLabel(entry) }}
              </td>
              <td
                class="px-4 py-3 text-ink-gray-5 text-sm text-right tabular-nums whitespace-nowrap"
                :title="entry.logged_at"
              >
                {{ activityTime(entry) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="hasMore"
        class="flex justify-center border-outline-gray-2 p-2 border-t shrink-0"
      >
        <Button variant="subtle" :loading="loadingMore" @click="loadMore(currentFilters)">
          Load more
        </Button>
      </div>
    </div>

    <div v-else class="flex flex-col flex-1 justify-center items-center gap-2 text-ink-gray-4">
      <span class="lucide-inbox size-8" />
      <p class="text-sm">No activity found.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, ErrorMessage, FormControl, LoadingText } from 'frappe-ui'
import { useActivities } from '@/composables/activities/useActivities'
import {
  activityActorLabel,
  activityLabel,
  activityResourceLabel,
  activityResourceRoute,
  activityTime,
  activityTypeMeta,
  activityTypeOptions,
} from '@/utils/activityFormat'

const route = useRoute()
const router = useRouter()
const { activities, loading, loadingMore, error, hasMore, load, loadMore } = useActivities()

const typeFilter = ref('')

const siteFilter = computed(() => (typeof route.query.site === 'string' ? route.query.site : ''))
const currentFilters = computed(() => ({
  type: typeFilter.value || undefined,
  site: siteFilter.value || undefined,
}))

function reload() {
  load(currentFilters.value)
}

function clearSiteFilter() {
  router.replace({ name: 'Activity' })
}

watch(siteFilter, reload)
onMounted(reload)
</script>
