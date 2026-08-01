<template>
  <ActionDialog
    v-model:open="open"
    title="Uninstall App"
    :subject="{ name: app?.name, label: appLabel, badge: app?.label, description: app?.description, logo: app?.logo_url }"
    :warning="{
      title: `This can't be undone.`,
      message: `Every doctype ${appLabel} owns is dropped from ${siteName}, along with the records in it. Back the site up first if you need the data.`,
    }"
    :error="error"
    confirm-label="Uninstall"
    confirm-theme="red"
    :loading="uninstalling"
    @confirm="confirmUninstall"
  >
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
  siteName: { type: String, required: true },
})
const open = defineModel('open')
const router = useRouter()

const uninstalling = ref(false)
const error = ref('')

const appLabel = computed(() => props.app?.title || props.app?.name || '')

watch(open, (isOpen) => {
  if (isOpen) error.value = ''
})

async function confirmUninstall() {
  if (!props.app || uninstalling.value) return
  error.value = ''
  uninstalling.value = true
  try {
    const result = await sitesApi.apps.remove(props.siteName, props.app.name)
    if (!result.task_id) throw new Error(apiErrorMessage(result, 'Uninstall failed.'))
    open.value = false
    openTaskDetailPage(router, result.task_id)
  } catch (caught) {
    error.value = caught.message || 'Could not start uninstall.'
  } finally {
    uninstalling.value = false
  }
}
</script>
