<template>
  <Dialog v-model="open" title="Import app from GitHub" size="md">
    <template #default>
      <div class="space-y-4">
        <!-- The pill span has no data-slot; without w-full the highlight stays content-width. -->
        <TabButtons
          v-model="tab"
          :options="tabOptions"
          size="md"
          class="w-full [&>div]:w-full [&_[data-slot=tab-button]>span]:w-full"
        />

        <div>
          <template v-if="tab === 'public'">
            <div class="flex items-end gap-2">
              <FormControl
                label="Repository URL"
                type="text"
                v-model="repo"
                class="flex-1"
                placeholder="https://github.com/frappe/crm"
              />
              <Combobox
                v-if="fetched"
                label="Branch"
                v-model="branch"
                :options="branchOptions"
                :loading="fetching"
                allowCustomValue
                placeholder="Search or type a branch…"
                emptyText="No matching branch. Type one to use it."
                class="w-40 shrink-0"
              />
            </div>
          </template>

          <template v-else>
            <p v-if="!gitStatus" class="text-ink-gray-5 text-sm">Loading…</p>
            <Alert
              v-else-if="!gitConnected"
              theme="yellow"
              title="No GitHub account connected"
              :dismissible="false"
            />
            <template v-else>
              <div
                class="flex items-center gap-2 bg-surface-gray-1 px-3 py-2 border rounded-lg border-outline-gray-2"
              >
                <span class="text-ink-gray-7 text-sm">
                  Connected as
                  <span class="font-medium text-ink-gray-9">{{ gitStatus.username }}</span>
                </span>
              </div>
              <div v-if="reposLoading" class="flex justify-center items-center h-32">
                <LoadingText />
              </div>
              <div v-else class="flex items-end gap-2 mt-2">
                <Combobox
                  label="Repository"
                  v-model="repo"
                  :options="repoOptions"
                  class="flex-1"
                  placeholder="Search repositories…"
                  emptyText="No repositories found."
                />
                <Combobox
                  v-if="fetched"
                  label="Branch"
                  v-model="branch"
                  :options="branchOptions"
                  :loading="fetching"
                  placeholder="Search branches…"
                  class="w-40 shrink-0"
                />
              </div>
            </template>
          </template>

          <!-- Progress, success and error share one hint slot under the input. -->
          <ErrorMessage v-if="error" :message="error" class="mt-1.5" />
          <p v-else-if="fetching" class="mt-1.5 text-ink-gray-5 text-sm">Loading branches…</p>
          <p v-else-if="resolving" class="mt-1.5 text-ink-gray-5 text-sm">Checking repository…</p>
          <p
            v-else-if="foundName"
            class="mt-1.5 flex items-center gap-1 text-ink-green-8 text-sm"
          >
            <span class="size-3.5 shrink-0 lucide-check"></span>
            Found {{ foundName
            }}<template v-if="siteName">, will be installed on {{ siteName }}</template>
          </p>
        </div>

        <div class="flex justify-end gap-2">
          <Button variant="subtle" @click="open = false">Cancel</Button>
          <Button v-if="needsGithubConnection" variant="solid" @click="goToGithubSettings"
            >Connect GitHub</Button
          >
          <Button v-else variant="solid" :disabled="!canSubmit" :loading="adding" @click="submit">
            {{ siteName ? 'Import and install' : 'Import app' }}
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Alert,
  Button,
  Combobox,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingText,
  TabButtons,
} from 'frappe-ui'
import { apiErrorMessage } from '@/api/client'
import { appsApi } from '@/api/apps'
import { gitApi } from '@/api/git'
import { openTaskDetailPage } from '@/utils/taskRoute'

const props = defineProps({
  // When set, the fetched app is also installed on this site.
  siteName: { type: String, default: '' },
})
const open = defineModel('open')
const router = useRouter()

const tab = ref('public')
const tabOptions = [
  { label: 'Public repository', value: 'public', class: 'flex-1' },
  { label: 'Your GitHub account', value: 'private', class: 'flex-1' },
]
const repo = ref('')
const branch = ref('')
const fetched = ref(false)
const fetching = ref(false)
const branches = ref([])
const branchOptions = computed(() => branches.value.map((b) => ({ label: b, value: b })))

const gitStatus = ref(null)
const gitConnected = computed(() =>
  Boolean(gitStatus.value?.connected && gitStatus.value?.is_token_valid),
)
const repos = ref([])
const reposLoading = ref(false)
const repoOptions = computed(() =>
  repos.value.map((r) => ({ label: r.full_name, value: r.clone_url })),
)

const adding = ref(false)
const error = ref('')

const needsGithubConnection = computed(
  () => tab.value === 'private' && Boolean(gitStatus.value) && !gitConnected.value,
)

function goToGithubSettings() {
  open.value = false
  router.push({ name: 'Settings', params: { section: 'general', subSection: 'github' } })
}

const resolving = ref(false)
const foundName = ref('')
const canSubmit = computed(() =>
  Boolean(repo.value.trim() && branch.value.trim() && foundName.value && !resolving.value),
)

watch(open, (isOpen) => {
  if (isOpen) reset()
})
watch(tab, reset)
// Accepts scheme-less URLs; every API call goes through normalizedRepo.
const normalizedRepo = computed(() => {
  const url = repo.value.trim().replace(/\/+$/, '')
  if (!url) return ''
  return /^https?:\/\//i.test(url) ? url : `https://${url}`
})

// host/owner/repo, with or without a scheme.
const REPO_PATTERN = /^(https?:\/\/)?[^/\s]+\.[^/\s]+\/[^/\s]+\/[^/\s]+$/

// Auto-fetch once the URL looks complete.
let repoDebounce
watch(repo, (value) => {
  fetched.value = false
  branches.value = []
  foundName.value = ''
  if (tab.value !== 'public') return
  clearTimeout(repoDebounce)
  if (!REPO_PATTERN.test(value.trim().replace(/\/+$/, ''))) return
  const url = normalizedRepo.value
  repoDebounce = setTimeout(() => loadBranchesFor(url), 600)
})

function reset() {
  clearTimeout(repoDebounce)
  repo.value = ''
  branch.value = ''
  fetched.value = false
  branches.value = []
  foundName.value = ''
  error.value = ''
  if (tab.value === 'private' && !gitStatus.value) loadGitStatus()
}

async function loadBranchesFor(url) {
  fetching.value = true
  error.value = ''
  try {
    const d = await gitApi.branches(url)
    if (d.branches) {
      branches.value = d.branches
      branch.value = d.branches[0] || ''
      fetched.value = true
    } else {
      error.value = apiErrorMessage(d, 'Could not load branches.')
    }
  } catch (e) {
    error.value = e.message
  } finally {
    fetching.value = false
  }
}

async function loadGitStatus() {
  gitStatus.value = await gitApi.status()
  if (gitConnected.value) {
    reposLoading.value = true
    try {
      const d = await gitApi.repos()
      if (Array.isArray(d)) repos.value = d
    } finally {
      reposLoading.value = false
    }
  }
}

watch(
  () => (tab.value === 'private' ? repo.value : null),
  (cloneUrl) => {
    if (cloneUrl) loadBranchesFor(cloneUrl)
  },
)

watch(branch, () => {
  if (repo.value.trim() && branch.value.trim()) resolveApp()
})

async function resolveApp() {
  resolving.value = true
  foundName.value = ''
  error.value = ''
  try {
    const d = await gitApi.resolve(normalizedRepo.value, branch.value.trim())
    if (d.name) foundName.value = d.name
    else error.value = apiErrorMessage(d, 'Could not find a Frappe app in this repository.')
  } catch (e) {
    error.value = e.message
  } finally {
    resolving.value = false
  }
}

async function submit() {
  if (!canSubmit.value || adding.value) return
  adding.value = true
  error.value = ''
  try {
    const result = await appsApi.add({
      name: foundName.value,
      repo: normalizedRepo.value,
      branch: branch.value.trim(),
      sites: props.siteName ? [props.siteName] : [],
    })
    if (!result.task_id) throw new Error(apiErrorMessage(result, 'Could not import app.'))
    open.value = false
    openTaskDetailPage(router, result.task_id)
  } catch (caught) {
    error.value = caught.message || 'Could not import app.'
  } finally {
    adding.value = false
  }
}
</script>
