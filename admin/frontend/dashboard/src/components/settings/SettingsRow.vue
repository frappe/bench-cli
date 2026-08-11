<template>
  <!-- `as="button"` when the row itself is the control. A row whose slot already
       holds one stays a div and forwards the click: a control nested in a button
       is invalid markup, and the inner one stops receiving its own clicks. -->
  <component
    :is="as"
    :type="as === 'button' ? 'button' : undefined"
    class="flex justify-between items-center gap-x-2.5 px-2.5 py-3"
    :class="interactive ? 'w-full rounded-4 transition-colors cursor-pointer text-left hover:bg-surface-alpha-gray-1' : ''"
  >
    <div class="flex flex-col gap-1">
      <!-- Matches frappe-ui's InputLabel (text-base) / InputDescription (text-p-sm). -->
      <p class="font-medium text-ink-gray-8 text-base">{{ label }}</p>
      <p v-if="description" class="text-ink-gray-6 text-p-sm">{{ description }}</p>
    </div>
    <div class="ml-4 shrink-0">
      <slot />
    </div>
  </component>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  description: { type: String, default: '' },
  as: { type: String, default: 'div', validator: (as) => ['div', 'button'].includes(as) },
  interactive: { type: Boolean, default: false },
})
</script>
