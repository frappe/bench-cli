<template>
  <div v-if="loading" class="flex justify-center py-12">
    <LoadingText />
  </div>
  <div v-else-if="error" class="py-12">
    <ErrorMessage :message="error" />
  </div>
  <div v-else-if="site" class="mx-auto w-full max-w-3xl">
    <!-- Hero -->
    <div class="relative -mx-4 sm:-mx-6 -mt-6 px-4 sm:px-6 pt-6 pb-7 overflow-hidden">
      <div class="absolute inset-0 pointer-events-none dot-field" aria-hidden="true" />
      <div
        class="relative flex justify-between items-center gap-3 mt-2 bg-surface-base p-2 sm:p-4 border rounded-xl border-outline-gray-2"
      >
        <div class="flex items-center gap-3 min-w-0">
          <span
            class="place-items-center grid bg-surface-gray-2 rounded-lg size-9 sm:size-10 text-ink-gray-6 shrink-0"
          >
            <span class="size-4 sm:size-5 lucide-globe" />
          </span>
          <div class="min-w-0">
            <div class="flex items-center gap-2 min-w-0">
              <h1 class="font-medium text-ink-gray-9 text-lg truncate">
                {{ site.name }}
              </h1>
              <Badge
                :label="statusLabel"
                :theme="statusBadgeTheme"
                variant="subtle"
                size="md"
                class="shrink-0"
              />
            </div>
            <div class="hidden sm:flex items-center gap-1.5 mt-1 text-ink-gray-5 text-sm">
              <span class="size-3.5 lucide-box" />
              {{ version || 'Version -' }}
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <Button size="sm" class="hidden sm:flex" @click="goToMarketplace">
            <template #prefix><span class="size-4 lucide-plus" /></template>
            Install app
          </Button>
          <Dropdown :options="menuOptions" placement="bottom-end">
            <template #default="{ open }">
              <Button variant="subtle" size="sm" :active="open">
                <span class="size-4 lucide-ellipsis" />
              </Button>
            </template>
          </Dropdown>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <TabButtons v-model="activeTab" :options="tabs" />

    <!-- Sections -->
    <SiteApps v-if="activeTab === 'apps'" :site-name="siteName" />
    <SiteBackups v-else-if="activeTab === 'backups'" :site-name="siteName" />
    <SiteConfig v-else-if="activeTab === 'config'" :site-name="siteName" />
    <SiteSettings v-else-if="activeTab === 'settings'" :site-name="siteName" />
  </div>

  <AppActionDialog
    v-if="appAction"
    v-model:open="showAppAction"
    :app-name="appAction.app"
    :action="appAction.action"
    :site-name="siteName"
  />

  <Teleport defer to="#header-actions">
    <Button
      :variant="site?.setup_complete ? 'subtle' : 'solid'"
      size="sm"
      :loading="settingUpSite"
      @click="site?.setup_complete ? openSite() : setupSite()"
    >
      <template #prefix><span class="size-4 lucide-external-link" /></template>
      <span class="hidden sm:inline">{{ site?.setup_complete ? 'Open site' : 'Setup site' }}</span>
      <span class="sm:hidden">{{ site?.setup_complete ? 'Open' : 'Setup' }}</span>
    </Button>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, Dropdown, ErrorMessage, LoadingText, TabButtons, toast } from 'frappe-ui'
import SiteApps from '@/components/sites/Apps.vue'
import SiteBackups from '@/components/sites/Backups.vue'
import SiteConfig from '@/components/sites/Config.vue'
import SiteSettings from '@/components/sites/Settings.vue'
import AppActionDialog from '@/components/sites/AppActionDialog.vue'
import { apiErrorMessage } from '@/api/client'
import { useBreadcrumbs } from '@/composables/common/useBreadcrumbs'
import { useSite } from '@/composables/sites/useSite'
import { useBench } from '@/composables/benches/useBench'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { openTaskDetailPage } from '@/utils/taskRoute'

const route = useRoute()
const router = useRouter()
const siteName = route.params.name

const { setBreadcrumbs } = useBreadcrumbs()
const { site, loading, error, status, load, reload, login, backup } = useSite(siteName)
const { version, load: loadBench } = useBench()

setBreadcrumbs([{ label: 'Sites', route: { name: 'Sites' } }, { label: siteName }])

const STATUS_THEMES = { online: 'green', broken: 'red', offline: 'orange', provisioning: 'blue' }
const STATUS_LABELS = {
  online: 'Live',
  broken: 'Broken',
  offline: 'Paused',
  provisioning: 'Creating',
}

const statusLabel = computed(() => STATUS_LABELS[status.value] ?? status.value)
const statusBadgeTheme = computed(() => STATUS_THEMES[status.value] ?? 'gray')

const tabs = [
  { value: 'apps', label: 'Apps' },
  { value: 'backups', label: 'Backups' },
  { value: 'config', label: 'Config' },
  { value: 'settings', label: 'Settings' },
]

const VALID_TABS = tabs.map((t) => t.value)
const activeTab = ref(VALID_TABS.includes(route.params.tab) ? route.params.tab : 'apps')

watch(activeTab, (tab) => {
  router.replace({ name: 'SiteDetail', params: { name: siteName, tab } })
})

watch(
  () => route.params.tab,
  (tab) => {
    if (tab && VALID_TABS.includes(tab) && tab !== activeTab.value) activeTab.value = tab
  },
)

const tabLabel = computed(() => tabs.find((t) => t.value === activeTab.value)?.label ?? '')
watchEffect(() => {
  if (site.value) document.title = `${site.value.name} | ${tabLabel.value}`
})

const APP_ACTIONS = ['install-app', 'uninstall-app']
const appAction = computed(() => {
  const app = route.query.app
  const action = route.query.action
  if (typeof app !== 'string' || !APP_ACTIONS.includes(action)) return null
  return { app, action }
})
const showAppAction = ref(false)
watch(
  appAction,
  (value) => {
    showAppAction.value = Boolean(value)
  },
  { immediate: true },
)
watch(showAppAction, (open) => {
  if (open) return
  router.replace({ name: 'SiteDetail', params: { name: siteName, tab: activeTab.value } })
})

const isMobile = useIsMobile()

function openSite() {
  window.open(`https://${site.value.name}`, '_blank')
}

const settingUpSite = ref(false)
async function setupSite() {
  settingUpSite.value = true
  try {
    await login()
  } catch (caught) {
    toast.error(caught.message || 'Could not open the setup wizard')
  } finally {
    settingUpSite.value = false
  }
}

function goToMarketplace() {
  router.push({ path: '/marketplace', query: { site: siteName } })
}

function loginAsAdmin() {
  toast.promise(login(), {
    loading: 'Logging in as admin',
    success: 'Logged in as admin',
    error: 'Could not log in as admin',
  })
}

async function backupNow() {
  try {
    const result = await backup()
    if (result.ok) openTaskDetailPage(router, result.task_id)
    else toast.error(apiErrorMessage(result, 'Could not start backup'))
  } catch (caught) {
    toast.error(caught.message || 'Could not start backup')
  }
}

const menuOptions = computed(() => [
  ...(isMobile.value
    ? [{ label: 'Install app', icon: 'lucide-plus', onClick: goToMarketplace }]
    : []),
  { label: 'Login as admin', icon: 'lucide-log-in', onClick: loginAsAdmin },
  { label: 'Back up now', icon: 'lucide-archive', onClick: backupNow },
  {
    label: 'View analytics',
    icon: 'lucide-chart-line',
    onClick: () =>
      router.push({ name: 'Analytics', query: { view: 'site', window: '24h', site: siteName } }),
  },
  {
    label: 'View jobs',
    icon: 'lucide-list-checks',
    onClick: () => router.push({ name: 'Tasks', query: { site: site.value.name } }),
  },
])

// Provisioning and a pending setup wizard both resolve without us: poll quietly
// until they do, so the badge and the header button settle on their own.
const POLL_INTERVAL_MS = 5000
const isSettling = computed(
  () => status.value === 'provisioning' || (status.value === 'online' && !site.value.setup_complete),
)

let poll = null
watch(
  isSettling,
  (settling) => {
    if (settling && !poll) {
      poll = setInterval(reload, POLL_INTERVAL_MS)
    } else if (!settling && poll) {
      clearInterval(poll)
      poll = null
    }
  },
  { immediate: true },
)

watch(
  () => site.value?.setup_complete,
  (complete, wasComplete) => {
    if (complete && wasComplete === false) toast.success('Site setup is complete')
  },
)

onUnmounted(() => {
  if (poll) clearInterval(poll)
})

onMounted(() => {
  load()
  loadBench()
})
</script>

<style scoped>
.dot-field {
  background-image: radial-gradient(var(--outline-gray-3) 1.1px, transparent 1.3px);
  background-size: 12px 12px;
  background-position: -5px -5px;
  mask-image: linear-gradient(to bottom, rgb(0 0 0 / 0.95), transparent 100%);
}
</style>
