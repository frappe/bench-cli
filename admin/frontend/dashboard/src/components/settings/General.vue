<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else-if="openSection">
    <component :is="openSection.component" />
  </div>
  <div v-else>
    <ErrorMessage v-if="error" :message="error" class="mb-4" />
    <div class="divide-y divide-outline-alpha-gray-1">
      <SettingsRow label="Allow developer mode" description="Enables per-site developer mode and code editor.">
        <Switch
          :model-value="allowDeveloperMode"
          :disabled="saving"
          @update:model-value="toggleAllowDeveloperMode"
        />
      </SettingsRow>

      <SettingsRow
        v-for="section in sections"
        :key="section.id"
        :label="section.label"
        :description="section.description"
      >
        <!-- Icon-only: `label` is not rendered but becomes the accessible name. A
             plain aria-label attr would be overwritten by Button's own. -->
        <Button
          size="sm"
          variant="ghost"
          icon="lucide-chevron-right"
          :label="`${section.action || 'Manage'} ${section.label}`"
          @click="openSection = section"
        />
      </SettingsRow>

      <Version />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Button, ErrorMessage, Switch, toast } from 'frappe-ui'
import { settingsApi } from '@/api/settings'
import { useSession } from '@/composables/auth/useSession'
import SettingsRow from '@/components/settings/SettingsRow.vue'
import Version from '@/components/settings/Version.vue'
import { GENERAL_SECTIONS as sections } from '@/components/settings/sections'

const openSection = defineModel('openSection')

const { session } = useSession()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const allowDeveloperMode = ref(false)

async function toggleAllowDeveloperMode(value) {
  saving.value = true
  error.value = ''
  try {
    await settingsApi.update({ bench: { allow_developer_mode: value } })
    allowDeveloperMode.value = value
    session.developerMode = value
    toast.success(`Developer mode ${value ? 'allowed' : 'disallowed'}`)
  } catch (e) {
    error.value = e.message || 'Could not update developer mode setting.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    allowDeveloperMode.value = Boolean(data?.bench?.allow_developer_mode)
  } catch {
    error.value = 'Could not load settings.'
  } finally {
    loading.value = false
  }
})
</script>
