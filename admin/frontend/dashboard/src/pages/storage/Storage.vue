<script setup lang="ts">
import { Button, ErrorMessage, Skeleton } from 'frappe-ui'

import { h, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { monitorApi } from '@/api/monitor'

import FCLogo from '@/components/icons/FC.vue'
import AppStorageCard from '@/components/storage/AppStorageCard.vue'
import DBStorageCard from '@/components/storage/DatabaseStorageCard.vue'

import type { StorageBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

const storageData = ref<StorageBreakdown | null>(null)
const loading = ref(false)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''

  try {
    storageData.value = await monitorApi.storage()
  } catch (e) {
    error.value = apiErrorMessage(e, 'Could not load storage breakdown.')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="mx-auto max-w-5xl">
    <div class="flex flex-wrap justify-between items-center gap-2 mb-4">
      <h2 class="flex items-center gap-2 font-medium text-ink-gray-8 text-lg">
        <span class="size-4 lucide-hard-drive" />
        Disk usage
      </h2>

      <span v-if="storageData" class="-mr-0.5"> {{ formatBytes(storageData.disk_used) }} </span>

      <span v-if="storageData" class="text-ink-gray-6">
        of {{ formatBytes(storageData.disk_total) }} used
      </span>

      <Button
        class="ml-auto"
        variant="ghost"
        size="sm"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        :loading="loading"
        @click="load"
      />

      <Button :iconLeft="h(FCLogo, { class: 'size-4' })"> Manage Storage </Button>
    </div>

    <div
      v-if="loading && !storageData"
      class="bg-surface-base border border-outline-gray-2 rounded-7 overflow-hidden"
    >
      <div
        class="divide-y lg:divide-x lg:divide-y-0 grid grid-cols-1 divide-outline-gray-2 lg:grid-cols-2"
      >
        <div v-for="col in 2" :key="col" class="flex flex-col gap-3 p-5">
          <Skeleton class="rounded-full w-full h-5" />
          <Skeleton
            v-for="row in 4"
            :key="row"
            class="h-3.5 rounded-4"
            :class="row % 2 ? 'w-full' : 'w-2/3'"
          />
        </div>
      </div>
    </div>

    <ErrorMessage v-else-if="error" :message="error" />

    <div
      v-else-if="storageData"
      class="bg-surface-base border border-outline-gray-2 rounded-7 fade-in overflow-hidden"
    >
      <div
        class="divide-y lg:divide-x lg:divide-y-0 grid grid-cols-1 divide-outline-gray-2 lg:grid-cols-2"
      >
        <DBStorageCard
          :data="storageData.database"
          :disk-total="storageData.disk_total"
          @purged="load"
        />
        <AppStorageCard :data="storageData.bench" :disk-total="storageData.disk_total" />
      </div>
    </div>
  </section>
</template>
