<template>
  <Dialog v-model="open" :title="title" :size="size">
    <template #default>
      <div class="space-y-4">
        <slot name="subject">
          <div v-if="subject" class="flex items-center gap-3">
            <Avatar v-if="subject.icon" size="xl" shape="square">
              <span class="size-4 text-ink-gray-7" :class="subject.icon" />
            </Avatar>
            <AppIcon
              v-else
              :name="subject.name || subject.label"
              :label="subject.label"
              :logo="subject.logo || ''"
              size="xl"
            />
            <div class="min-w-0">
              <div class="flex items-center gap-1.5">
                <p class="font-medium text-ink-gray-8 text-base truncate">{{ subject.label }}</p>
                <span v-if="subject.badge" class="text-ink-gray-5 text-xs shrink-0">
                  {{ subject.badge }}
                </span>
              </div>
              <p v-if="subject.description" class="text-ink-gray-5 text-p-sm line-clamp-2">
                {{ subject.description }}
              </p>
            </div>
          </div>
        </slot>

        <slot />

        <div
          v-if="warning"
          class="flex items-start gap-3 bg-surface-red-1 p-3 border border-outline-red-2 rounded-6"
        >
          <span class="mt-0.5 size-4 text-ink-red-6 lucide-alert-triangle shrink-0" />
          <div class="min-w-0 text-p-sm text-ink-red-8">
            <p class="font-medium">{{ warning.title }}</p>
            <p v-if="warning.message" class="mt-0.5 leading-5">{{ warning.message }}</p>
          </div>
        </div>

        <slot name="after-warning" />

        <ErrorMessage v-if="error" :message="error" />

        <div class="flex justify-end gap-2">
          <Button variant="subtle" @click="open = false">{{ cancelLabel }}</Button>
          <Button
            variant="solid"
            :theme="confirmTheme"
            :loading="loading"
            :disabled="disabled"
            @click="emit('confirm')"
          >
            {{ confirmLabel }}
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Avatar, Button, Dialog, ErrorMessage } from 'frappe-ui'
import AppIcon from '@/components/apps/AppIcon.vue'

defineProps({
  title: { type: String, required: true },
  size: { type: String, default: 'md' },
  // { label, description, badge, icon } - `icon` picks a lucide tile, otherwise
  // the app logo is used via { name, logo }.
  subject: { type: Object, default: null },
  // { title, message } rendered as the destructive-action callout.
  warning: { type: Object, default: null },
  error: { type: String, default: '' },
  confirmLabel: { type: String, required: true },
  confirmTheme: { type: String, default: 'gray' },
  cancelLabel: { type: String, default: 'Cancel' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const open = defineModel('open')
const emit = defineEmits(['confirm'])
</script>
