<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed, onMounted, ref, watch } from 'vue'

import { ListView } from 'frappe-ui/experimental'

import {
  Badge,
  Button,
  Dropdown,
  ErrorMessage,
  FormControl,
  TabButtons,
  toast,
} from 'frappe-ui'

import EmptyState from '@/components/common/EmptyState.vue'
import SiteSkeleton from '@/components/sites/SiteSkeleton.vue'
import NewSiteDialog from '@/components/sites/NewSiteDialog.vue'
import StickyToolbar from '@/components/common/StickyToolbar.vue'

import { sitesApi } from '@/api/sites'
import { apiErrorMessage } from '@/api/client'
import { openSiteLogin } from '@/utils/siteLogin'
import { openTaskDetailPage } from '@/utils/taskRoute'
import { useSites } from '@/composables/sites/useSites'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { useSiteStorage } from '@/composables/sites/useSiteStorage'
import { useBreadcrumbs } from '@/composables/common/useBreadcrumbs'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()
const { setBreadcrumbs } = useBreadcrumbs()
const { sites, loading, error, load } = useSites()
const { load: loadStorage, storageLabel } = useSiteStorage()

const search = ref('')
const statusFilter = ref('all')
const view = ref('grid')

const viewOptions = [
  { value: 'grid', icon: 'lucide-layout-grid' },
  { value: 'list', icon: 'lucide-list' },
]

const SITE_STATUS = {
  broken: { label: 'Broken', theme: 'red' },
  offline: { label: 'Paused', theme: 'orange' },
  provisioning: { label: 'Creating', theme: 'blue' },
}

const statusOptions = [
  { label: 'Status', value: 'all' },
  { label: 'Active', value: 'online' },
  { label: 'Broken', value: 'broken' },
  { label: 'Paused', value: 'offline' },
  { label: 'Creating', value: 'provisioning' },
]

const siteStatus = (site) => {
  // Provisioning wins over "offline": the site dir/site_config.json may not
  // exist yet in the earliest moments of a new-site/reinstall task.
  if (site.provisioning) return 'provisioning'
  if (!site.exists) return 'offline'
  if (site.broken) return 'broken'
  return 'online'
}

const statusBadge = (site) => SITE_STATUS[siteStatus(site)]

const appsLabel = (site) => {
  const count = site.active_apps?.length || 0
  return count === 1 ? '1 app' : `${count} apps`
}

// Storage lands after the list, so a card shows its app count alone until then.
const metaLabel = (site) => {
  const used = storageLabel(site.name)
  return used ? `${used} · ${appsLabel(site)}` : appsLabel(site)
}

const isFiltered = computed(() => Boolean(search.value.trim()) || statusFilter.value !== 'all')

// The total, not the filtered list: filtering down to ten must not hide the controls.
const showToolbar = computed(() => sites.value.length > 10)

const filteredSites = computed(() => {
  const query = search.value.toLowerCase().trim()
  return sites.value.filter((site) => {
    const matchesSearch = !query || site.name.toLowerCase().includes(query)
    const matchesStatus = statusFilter.value === 'all' || siteStatus(site) === statusFilter.value
    return matchesSearch && matchesStatus
  })
})

const hasCount = computed(() => !loading.value || sites.value.length > 0)

const listColumns = [
  { label: 'Site', key: 'site', align: 'left', width: 3 },
  { label: 'Status', key: 'status', align: 'left', width: 1.5 },
  { label: 'Storage', key: 'storage', align: 'left', width: 1.5 },
  { label: 'Apps', key: 'apps', align: 'left', width: 1.5 },
  { label: '', key: 'actions', align: 'right', width: '3rem' },
]

const listRows = computed(() =>
  filteredSites.value.map((site) => ({
    name: site.name,
    site,
    storage: storageLabel(site.name),
    apps: appsLabel(site),
  })),
)

const loginAsAdmin = async (site) => {
  return openSiteLogin(() => sitesApi.loginLink(site.name), {
    onHint: (hint) => toast.info(hint),
  })
}

const openSite = (site) => {
  toast.promise(loginAsAdmin(site), {
    loading: 'Logging in as admin',
    success: 'Logged in as admin',
    error: (caught) => caught?.message || 'Could not log in as admin',
  })
}

const backupNow = async (site) => {
  try {
    const result = await sitesApi.backups.create(site.name)
    if (result.ok) openTaskDetailPage(router, result.task_id)
    else toast.error(apiErrorMessage(result, 'Could not start backup'))
  } catch (caught) {
    toast.error(caught.message || 'Could not start backup')
  }
}

const siteMenuOptions = (site) => {
  return [
    { label: 'Open site', icon: 'lucide-external-link', onClick: () => openSite(site) },
    { label: 'Back up now', icon: 'lucide-archive', onClick: () => backupNow(site) },
    {
      label: 'View analytics',
      icon: 'lucide-chart-line',
      onClick: () =>
        router.push({ name: 'Analytics', query: { view: 'site', site: site.name } }),
    },
    {
      label: 'View jobs',
      icon: 'lucide-list-checks',
      onClick: () => router.push({ name: 'Tasks', query: { site: site.name } }),
    },
  ]
}

const showCreate = ref(false)

watch(
  () => route.query.new,
  (value) => {
    if (!value) return
    showCreate.value = true
    router.replace({ name: 'Sites' })
  },
  { immediate: true },
)

onMounted(() => {
  load()
  loadStorage(true)
})
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <!-- Bar -->
    <StickyToolbar v-if="showToolbar" class="flex items-center gap-2">
      <!-- Search text bar -->
      <FormControl
        v-model="search"
        type="text"
        placeholder="Search"
        :size="isMobile ? 'md' : 'sm'"
        class="flex-1"
      >
        <template #prefix>
          <span class="size-4 text-ink-gray-5 lucide-search" />
        </template>
      </FormControl>

      <!-- Status filter -->
      <FormControl
        v-model="statusFilter"
        type="select"
        :options="statusOptions"
        :size="isMobile ? 'md' : 'sm'"
        class="max-w-24 sm:max-w-32"
      />
      <!-- List view type -->
      <TabButtons
        v-model="view"
        :options="viewOptions"
        :size="isMobile ? 'md' : 'sm'"
        class="hidden sm:block"
      />
    </StickyToolbar>

    <!-- Always the grid shape: `view` resets to 'grid' on every mount, and a
         mount is the only time this is loading. -->
    <div v-if="loading" class="gap-3 grid grid-cols-1 md:grid-cols-2 mt-1">
      <SiteSkeleton v-for="index in 4" :key="index" :index="index - 1" />
    </div>

    <div v-else-if="error" class="mt-16">
      <ErrorMessage :message="error" />
    </div>

    <div v-else-if="filteredSites.length" class="mt-1">
      <!-- A single result keeps the full width. -->
      <div
        v-if="view === 'grid'"
        class="gap-3 grid grid-cols-1"
        :class="filteredSites.length > 1 ? 'md:grid-cols-2' : ''"
      >
        <!-- Site Card -->
        <div
          v-for="site in filteredSites"
          :key="site.name"
          class="flex items-center gap-3 bg-surface-base p-2 sm:px-3 sm:py-2 border rounded-6 border-outline-gray-2 hover:border-outline-gray-3 transition-colors"
        >
          <RouterLink
            :to="{ name: 'SiteDetail', params: { name: site.name } }"
            class="flex flex-1 items-center gap-3 min-w-0 no-underline"
          >
            <!-- Icon -->
            <div
              class="place-items-center grid bg-surface-gray-2 rounded-4 size-8 text-ink-gray-6 shrink-0"
            >
              <span class="size-4 lucide-globe"></span>
            </div>

            <div class="flex-1 min-w-0">
              <!-- First Line -->
              <div class="gap-2 grid grid-cols-[3fr_1fr]">
                <div class="flex items-center gap-1.5 min-w-0">
                  <!-- Site Name -->
                  <span class="font-medium text-ink-gray-9 text-base truncate">
                    {{ site.name }}
                  </span>

                  <!-- Status -->
                  <Badge
                    v-if="statusBadge(site)"
                    v-bind="statusBadge(site)"
                    variant="subtle"
                    size="sm"
                    class="shrink-0"
                  />
                </div>

                <div class="flex justify-end">
                  <!-- Actions Dropdown -->
                  <Dropdown :options="siteMenuOptions(site)">
                    <Button
                      variant="ghost"
                      size="xs"
                      icon="lucide-ellipsis"
                      label="Site actions"
                      tooltip="Actions"
                    />
                  </Dropdown>
                </div>
              </div>

              <!-- Second Line -->
              <p class="text-ink-gray-5 text-p-sm">
                {{ metaLabel(site) }}
              </p>
            </div>
          </RouterLink>
        </div>
      </div>

      <!-- List view -->
      <ListView
        v-else
        :columns="listColumns"
        :rows="listRows"
        row-key="name"
        :options="{ selectable: false, showTooltip: false }"
      >
        <template #cell="{ column, row, item }">
          <div v-if="column.key === 'site'" class="flex items-center min-w-0">
            <RouterLink
              :to="{ name: 'SiteDetail', params: { name: row.site.name } }"
              class="font-medium text-ink-gray-9 text-base no-underline truncate"
            >
              {{ row.site.name }}
            </RouterLink>
          </div>

          <div v-else-if="column.key === 'status'">
            <Badge
              v-if="statusBadge(row.site)"
              v-bind="statusBadge(row.site)"
              variant="subtle"
              size="sm"
            />
          </div>

          <div
            v-else-if="column.key === 'storage' || column.key === 'apps'"
            class="text-ink-gray-6 text-sm"
          >
            {{ item }}
          </div>

          <div v-else-if="column.key === 'actions'" class="flex justify-end">
            <Dropdown :options="siteMenuOptions(row.site)">
              <template #default="{ open }">
                <Button
                  variant="ghost"
                  size="sm"
                  :active="open"
                  icon="lucide-ellipsis"
                  label="Site actions"
                  tooltip="Actions"
                />
              </template>
            </Dropdown>
          </div>
        </template>
      </ListView>
    </div>

    <EmptyState
      v-else
      class="mt-4"
      icon="lucide-globe"
      :title="isFiltered ? 'No matching sites' : 'No sites yet'"
      :description="
        isFiltered
          ? 'No sites match your search or status filter.'
          : 'Create a site to get started on this bench.'
      "
    />
  </div>

  <Teleport v-if="hasCount" defer to="#header-badge">
    <Badge :label="filteredSites.length" theme="gray" variant="subtle" size="md" />
  </Teleport>

  <!-- New Site Button -->
  <Teleport defer to="#header-actions">
    <Button variant="solid" @click="showCreate = true">
      <template #prefix>
        <span class="size-4 lucide-plus" />
      </template>
      New site
    </Button>
  </Teleport>

  <NewSiteDialog
    v-model="showCreate"
    :sites="sites"
    @started="(taskId) => openTaskDetailPage(router, taskId)"
  />
</template>
