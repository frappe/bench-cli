<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <Spinner size="lg" class="text-ink-gray-4" />
  </div>
  <div v-else class="space-y-6">
    <div class="flex justify-end">
      <Button variant="subtle" icon-left="lucide-plus" @click="openAdd">Add</Button>
    </div>
    <div
      v-if="loadError"
      class="py-12 border border-dashed rounded-7 border-outline-red-2 text-ink-red-3 text-p-sm text-center"
    >
      {{ loadError }}
    </div>
    <EmptyState
      compact
      v-else-if="!rows.length"
      icon="lucide-key-round"
      title="No SSH keys"
      description="Add a public key to give its holder SSH access to this server."
    />
    <ListView
      v-else
      :columns="columns"
      :rows="rows"
      row-key="fingerprint"
      :options="{ selectable: false, showTooltip: false }"
    >
      <template #cell="{ column, row, item }">
        <div v-if="column.key === 'actions'" class="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            theme="red"
            icon="lucide-trash-2"
            label="Remove SSH key"
            tooltip="Remove SSH key"
            @click="promptRemove(row)"
          />
        </div>
        <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
      </template>
    </ListView>
  </div>

  <Dialog v-model="showAdd" :options="{ title: 'Add SSH key', size: 'md' }">
    <template #body-content>
      <FormControl
        type="textarea"
        label="Public key"
        v-model="newKey"
        :rows="3"
        placeholder="ssh-ed25519 AAAA… user@host"
      />
      <ErrorMessage v-if="error" :message="error" class="mt-2" />
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showAdd = false">Cancel</Button>
        <Button variant="solid" :loading="adding" :disabled="!newKey.trim()" @click="add">
          Add key
        </Button>
      </div>
    </template>
  </Dialog>

  <Dialog v-model="showRemove" :options="{ title: 'Remove SSH key', size: 'md' }">
    <template #body-content>
      <p v-if="isLastKey" class="text-ink-gray-7 text-p-base">
        This is the last authorized key. It can't be removed, or you'd lose SSH access to this
        server.
      </p>
      <p v-else class="text-ink-gray-7 text-p-base">
        Remove <span class="font-semibold text-ink-gray-8 break-all">{{ removing?.label }}</span>?
        Whoever holds the matching private key loses SSH access.
      </p>
      <div v-if="!isLastKey" class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showRemove = false">Cancel</Button>
        <Button variant="solid" theme="red" :loading="removingBusy" @click="confirmRemove"
          >Remove</Button
        >
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl, Spinner, toast } from 'frappe-ui'
import { ListRowItem, ListView } from 'frappe-ui/experimental'
import EmptyState from '@/components/common/EmptyState.vue'
import { apiErrorMessage } from '@/api/client'
import { sshKeysApi } from '@/api/sshKeys'

// Numeric widths are fr units (ListView convention) so Name/Fingerprint stretch to
// fill the row instead of leaving dead space; actions stays a fixed icon-sized column.
const columns = [
  { label: 'Name', key: 'label', align: 'left', width: 1 },
  { label: 'Fingerprint', key: 'fingerprint', align: 'left', width: 2 },
  { label: '', key: 'actions', align: 'right', width: '3rem' },
]

const loading = ref(true)
const adding = ref(false)
const error = ref('')
const loadError = ref('')
const keys = ref([])
const newKey = ref('')
const showAdd = ref(false)
const showRemove = ref(false)
const removing = ref(null)
const removingBusy = ref(false)

const rows = computed(() =>
  keys.value.map((k) => ({ fingerprint: k.fingerprint, label: k.comment || 'Unnamed key' })),
)
const isLastKey = computed(() => rows.value.length <= 1)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    keys.value = (await sshKeysApi.list()).keys || []
  } catch (e) {
    loadError.value = e.message || 'Could not load SSH keys.'
  } finally {
    loading.value = false
  }
}

function openAdd() {
  newKey.value = ''
  error.value = ''
  showAdd.value = true
}

async function add() {
  adding.value = true
  error.value = ''
  try {
    const result = await sshKeysApi.add(newKey.value.trim())
    if (result.fingerprint) {
      showAdd.value = false
      toast.success('Key added')
      await load()
    } else {
      error.value = apiErrorMessage(result, 'Could not add key.')
    }
  } catch (e) {
    error.value = e.message || 'Could not add key.'
  } finally {
    adding.value = false
  }
}

function promptRemove(row) {
  removing.value = row
  showRemove.value = true
}

async function confirmRemove() {
  removingBusy.value = true
  try {
    const response = await sshKeysApi.remove(removing.value.fingerprint)
    if (response.ok) {
      toast.success('Key removed')
      showRemove.value = false
      await load()
    } else {
      toast.error(apiErrorMessage(await response.json(), 'Could not remove key.'))
    }
  } catch (e) {
    toast.error(e.message || 'Could not remove key.')
  } finally {
    removingBusy.value = false
  }
}

onMounted(load)
</script>
