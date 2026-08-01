<template>
  <ActionDialog
    v-model:open="open"
    :title="`Install ${appLabel} on`"
    :error="error"
    confirm-label="Install"
    :loading="installing"
    :disabled="!selection || targetInstalled"
    @confirm="confirmInstall"
  >
    <SiteRow v-if="targetSite" :label="targetSite.name" selected :interactive="false">
      <template #suffix>
        <span class="w-20 text-ink-gray-5 text-sm text-right shrink-0">
          {{ siteMeta(targetSite) }}
        </span>
        <span
          v-if="targetInstalled"
          class="size-4 text-ink-gray-9 shrink-0 lucide-check"
          role="img"
          aria-label="Already installed"
        />
      </template>
    </SiteRow>

    <div v-else class="gap-1.5 grid max-h-80 overflow-y-auto">
      <SiteRow
        v-if="showAllSitesOption"
        label="All sites"
        icon="lucide-layout-grid"
        :selected="selection === 'all'"
        @click="selection = 'all'"
      >
        <template #suffix>
          <span class="w-20 text-ink-gray-5 text-sm text-right shrink-0">
            {{ installableSites.length }} sites
          </span>
        </template>
      </SiteRow>

      <SiteRow
        v-for="s in sites"
        :key="s.name"
        :label="s.name"
        :disabled="isInstalled(s)"
        :selected="selection === s.name"
        @click="selection = s.name"
      >
        <template #suffix>
          <span class="w-20 text-ink-gray-5 text-sm text-right shrink-0">
            {{ siteMeta(s) }}
          </span>
          <span
            v-if="isInstalled(s)"
            class="size-4 text-ink-gray-9 shrink-0 lucide-check"
            role="img"
            aria-label="Already installed"
          />
        </template>
      </SiteRow>

      <p v-if="!sites.length" class="py-6 text-ink-gray-5 text-p-sm text-center">
        No sites available on this bench.
      </p>
    </div>
  </ActionDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ActionDialog from '@/components/common/ActionDialog.vue'
import SiteRow from '@/components/sites/SiteRow.vue'
import { apiErrorMessage } from '@/api/client'
import { sitesApi } from '@/api/sites'
import { openTaskDetailPage } from '@/utils/taskRoute'

const props = defineProps({
  app: { type: Object, default: null },
  sites: { type: Array, default: () => [] },
  siteName: { type: String, default: '' },
})
const open = defineModel('open')
const router = useRouter()

const selection = ref(null)
const installing = ref(false)
const error = ref('')

const appLabel = computed(() => props.app?.title || props.app?.name || '')

const presetSite = computed(() => props.sites.find((s) => s.name === props.siteName) || null)
// A single-site bench behaves like a preset: shown for confirmation, never asked.
const soleSite = computed(() => (props.sites.length === 1 ? props.sites[0] : null))
const targetSite = computed(() => presetSite.value || soleSite.value)
const targetInstalled = computed(() => Boolean(targetSite.value && isInstalled(targetSite.value)))

watch(open, (isOpen) => {
  if (!isOpen) return
  selection.value = props.siteName || soleSite.value?.name || null
  error.value = ''
})

const installableSites = computed(() => props.sites.filter((s) => !isInstalled(s)))
// Hide "All sites" when there's only one site on the bench, or only one site left to install on.
const showAllSitesOption = computed(() => props.sites.length > 1 && installableSites.value.length > 1)

function isInstalled(site) {
  return Boolean(props.app && site.installed_apps?.includes(props.app.name))
}

function siteMeta(site) {
  const n = site.installed_apps?.length || 0
  return `${n} app${n === 1 ? '' : 's'}`
}

async function startInstall(site) {
  const result = await sitesApi.apps.install(site.name, {
    app: props.app.name,
  })
  if (!result.task_id)
    throw new Error(apiErrorMessage(result, `Could not install on ${site.name}.`))
  return result.task_id
}

async function installOnSite(name) {
  const site = props.sites.find((s) => s.name === name)
  if (!site) return
  const taskId = await startInstall(site)
  open.value = false
  openTaskDetailPage(router, taskId)
}

async function installOnAllSites() {
  const targets = installableSites.value
  if (!targets.length) return
  await Promise.all(targets.map((site) => startInstall(site)))
  open.value = false
  router.push({ name: 'Tasks' })
}

async function confirmInstall() {
  if (!selection.value || installing.value) return
  error.value = ''
  installing.value = true
  try {
    if (selection.value === 'all') await installOnAllSites()
    else await installOnSite(selection.value)
  } catch (caught) {
    error.value = caught.message || 'Could not start install.'
  } finally {
    installing.value = false
  }
}
</script>
