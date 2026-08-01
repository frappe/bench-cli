<template>
  <div class="mt-6">
    <div class="flex sm:flex-row flex-col gap-2">
      <FormControl
        v-model="searchModel"
        class="flex-1"
        type="text"
        placeholder="Search for any app"
      >
        <template #prefix>
          <LucideSearch class="size-4 text-ink-gray-5" />
        </template>
      </FormControl>

      <div class="flex gap-2">
        <Dropdown :options="worksWithMenu" placement="bottom-end">
          <template #default="{ open }">
            <Button class="[&>.truncate]:flex-1 [&>.truncate]:text-left" :active="open">
              <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
              {{ worksWithLabel }}
            </Button>
          </template>
        </Dropdown>

        <Button variant="subtle" @click="$emit('add-from-github')">
          <template #prefix><GithubMark class="size-4" /></template>
          Import app
        </Button>
      </div>
    </div>

    <!-- Scrolls rather than clips: TabButtons' rail is overflow-hidden and does not wrap. -->
    <div class="mt-3 overflow-x-auto">
      <TabButtons v-model="pillModel" :options="pillOptions" type="ghost" />
    </div>
  </div>
</template>

<script setup>
import { computed, h } from 'vue'
import { Button, Dropdown, FormControl, TabButtons } from 'frappe-ui'
import LucideSearch from '~icons/lucide/search'
import GithubMark from '@/components/icons/GithubMark.vue'
import { PILLS } from '@/utils/marketplaceCategories'

const props = defineProps({
  worksWithOptions: { type: Array, default: () => [] },
})
defineEmits(['add-from-github'])

const searchModel = defineModel('search', { type: String })
const pillModel = defineModel('pill', { type: String })
const worksWithModel = defineModel('worksWith', { type: String })

const pillOptions = PILLS.map((pill) => ({ label: pill, value: pill }))

function appLogo(option) {
  if (!option.logo_url) return null
  return () => h('img', { src: option.logo_url, class: 'size-4 rounded object-contain' })
}

const worksWithMenu = computed(() => [
  {
    label: 'Any app',
    icon: () => h('span', { class: 'size-4 text-ink-gray-6 lucide-layout-grid' }),
    onClick: () => (worksWithModel.value = ''),
  },
  ...props.worksWithOptions.map((option) => ({
    label: option.title,
    icon: appLogo(option),
    onClick: () => (worksWithModel.value = option.name),
  })),
])

const worksWithLabel = computed(() => {
  const selected = props.worksWithOptions.find((option) => option.name === worksWithModel.value)
  return selected ? selected.title : 'Works with'
})
</script>
