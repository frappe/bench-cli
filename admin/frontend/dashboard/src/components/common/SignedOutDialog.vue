<template>
  <!-- Teleported to body to clear the app's stacking context, and pointer-events-auto because
       an open frappe-ui Dialog sets pointer-events:none on <body>, which this would inherit. -->
  <Teleport to="body">
    <div
      v-if="signedOut"
      class="z-[9999] fixed inset-0 flex justify-center items-center bg-black-overlay-200 dark:bg-black-overlay-700 p-4 pointer-events-auto"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="signed-out-title"
    >
      <div
        class="flex flex-col items-start gap-4 bg-surface-elevation-1 shadow-2xl p-6 border border-outline-gray-1 rounded-7 w-full max-w-sm"
      >
        <div class="flex justify-center items-center bg-surface-gray-2 rounded-full size-9">
          <LucideLock class="size-4 text-ink-gray-6" />
        </div>
        <div class="flex flex-col gap-1">
          <h2 id="signed-out-title" class="font-semibold text-ink-gray-9 text-lg">
            You were signed out
          </h2>
          <!-- Deliberately says nothing about why: the cause is not the viewer's to know. -->
          <p class="text-ink-gray-5 text-p-base">Sign in again to continue.</p>
        </div>
        <Button class="w-full" variant="solid" @click="signInAgain">Sign in again</Button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { Button } from 'frappe-ui'
import LucideLock from '~icons/lucide/lock'
import { useSignedOut } from '@/composables/auth/useSignedOut'

const { signedOut } = useSignedOut()

function signInAgain() {
  // A full load, not a router push: it drops every stale in-memory session and view state.
  const redirect = `${window.location.pathname}${window.location.search}`
  window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
}
</script>
