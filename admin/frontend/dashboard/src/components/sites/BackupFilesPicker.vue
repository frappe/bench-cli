<script setup lang="ts">
const files = defineModel({
  default: () => ({ database: null, public_files: null, private_files: null }),
})

const FIELDS = [
  { key: 'database', label: 'Database', hint: '.sql.gz or .sql', accept: '.sql.gz,.sql,.gz' },
  {
    key: 'public_files',
    label: 'Public files',
    hint: 'files.tar (optional)',
    accept: '.tar,.tar.gz,.tgz',
  },
  {
    key: 'private_files',
    label: 'Private files',
    hint: 'private-files.tar (optional)',
    accept: '.tar,.tar.gz,.tgz',
  },
]

const pick = (key, event) => {
  files.value = { ...files.value, [key]: event.target.files?.[0] || null }
}

const fmtSize = (bytes) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="space-y-3">
    <div v-for="field in FIELDS" :key="field.key" class="space-y-1">
      <label class="block text-ink-gray-7 text-p-sm-medium" :for="`backup-${field.key}`">
        {{ field.label }}
        <span class="font-normal text-ink-gray-5">- {{ field.hint }}</span>
      </label>
      <input
        :id="`backup-${field.key}`"
        type="file"
        :accept="field.accept"
        class="block w-full text-ink-gray-7 text-p-sm file:mr-3 file:px-2.5 file:py-1 file:border-0 file:rounded-4 file:bg-surface-gray-2 file:text-ink-gray-8 file:text-p-sm hover:file:bg-surface-gray-3"
        @change="pick(field.key, $event)"
      />
      <p v-if="files[field.key]" class="text-ink-gray-5 text-xs">
        {{ files[field.key].name }} · {{ fmtSize(files[field.key].size) }}
      </p>
    </div>
  </div>
</template>
