<template>
  <div class="space-y-3" ref="root">
    <div class="flex justify-between items-start gap-4">
      <div class="min-w-0">
        <p class="font-medium text-ink-gray-8 text-base">Custom rules</p>
        <p class="mt-0.5 max-w-md text-ink-gray-5 text-p-sm">
          Checked before the managed rules, top to bottom.
        </p>
      </div>
      <Button class="shrink-0" variant="subtle" icon-left="lucide-plus" @click="addRule">
        Add rule
      </Button>
    </div>

    <EmptyState
      v-if="!rules.length"
      compact
      icon="lucide-list-filter"
      title="No custom rules"
      description="Add a rule to block or log requests by path, IP, method, header, and more."
    />

    <div
      v-if="rules.length"
      class="bg-surface-elevation-1 p-1 border border-outline-gray-2 rounded-6"
    >
      <div
        v-for="rule in rules"
        :key="keyOf(rule)"
        :data-rule-key="keyOf(rule)"
        class="rounded-4 ring-1 ring-inset transition-shadow"
        :class="[
          // Fast in, slow out. transition-shadow: a ring is box-shadow underneath.
          flaggedKey === keyOf(rule) ? 'ring-outline-red-3 duration-75' : 'ring-transparent duration-1000',
          dragKey === keyOf(rule) ? 'opacity-50' : '',
          // No dividers, so air below an open rule marks where its fields stop.
          // Below only: a top margin would shove the header down as it opens.
          isOpen(rule) ? 'mb-1 last:mb-0' : '',
        ]"
        @dragover.prevent="onDragOver(rule)"
      >
        <!-- The whole row toggles; interactive children stop the click. -->
        <div
          class="flex items-center gap-3 px-2.5 h-10 rounded-4 transition-colors cursor-pointer select-none hover:bg-surface-alpha-gray-1"
          @click="toggleOpen(rule)"
        >
          <button
            type="button"
            draggable="true"
            class="text-ink-gray-4 hover:text-ink-gray-6 cursor-grab shrink-0"
            aria-label="Drag to reorder"
            @click.stop
            @dragstart="onDragStart(rule, $event)"
            @dragend="onDragEnd"
          >
            <span class="block size-4 lucide-grip-vertical" />
          </button>
          <button
            type="button"
            class="flex flex-1 items-baseline gap-2 min-w-0 text-left"
            :aria-expanded="isOpen(rule)"
            @click.stop="toggleOpen(rule)"
          >
            <span
              class="min-w-0 font-medium text-base truncate"
              :class="rule.enabled ? 'text-ink-gray-8' : 'text-ink-gray-5'"
            >
              {{ rule.name || 'Untitled rule' }}
            </span>
            <span class="min-w-0 text-ink-gray-6 text-p-sm truncate">
              {{ ruleSummary(rule) }}
            </span>
            <!-- What the rule does outranks what it matches on: never truncate it. -->
            <span class="shrink-0 text-ink-gray-6 text-p-sm">→ {{ actionLabel(rule) }}</span>
          </button>
          <!-- The nginx renderer silently drops broken rules. -->
          <Badge v-if="ruleProblem(rule)" class="shrink-0" theme="amber">Incomplete</Badge>
          <!-- A bare Switch has no accessible name (attrs land on the wrapper);
               `label` gives the <label for> association, sr-only hides it. -->
          <Switch
            size="sm"
            class="shrink-0 [&_[data-slot='label']]:sr-only [&>div]:!gap-x-0 [&>div]:!py-0"
            label="Rule enabled"
            :model-value="rule.enabled"
            @click.stop
            @update:model-value="(v) => (rule.enabled = v)"
          />
        </div>

        <!-- Indent on the left only: the fields keep the header's right edge.
             pl clears the drag handle so the fields line up under the rule name. -->
        <div v-if="isOpen(rule)" class="space-y-4 pt-1 pr-2.5 pb-5 pl-[2.375rem]">
        <FormControl
          type="text"
          label="Rule name"
          v-model="rule.name"
          placeholder="Block /admin from outside the office"
        />

        <div class="space-y-3">
          <!-- All/Any only once there is something to combine. gap-1 is about a
               space at this size, so the row reads as a sentence. -->
          <div class="flex flex-wrap items-center gap-1 text-ink-gray-7 text-base">
            <!-- One phrase when there is no Select between the words, or the flex
                 gap reads as a double space. -->
            <template v-if="rule.conditions.length > 1">
              <span>When</span>
              <Select v-model="rule.match" :options="MATCH_OPTIONS" />
              <span>of the following match:</span>
            </template>
            <span v-else>When this matches:</span>
          </div>

          <!-- Anchored here, not to the group, so it clears the label whatever
               that row's height is - it grows when the All/Any select appears. -->
          <div class="relative space-y-3">
            <span
              aria-hidden="true"
              class="absolute left-1 -top-2 bottom-0 border-l border-outline-gray-3"
            />

            <div class="space-y-2 pl-5">
              <div
                v-for="(cond, ci) in rule.conditions"
                :key="keyOf(cond)"
                class="gap-2 grid grid-cols-1 sm:grid-cols-[10rem_11rem_minmax(0,1fr)_2rem] items-start"
              >
                <!-- Stacked inside the field column to keep rows aligned. -->
                <div class="space-y-1.5 min-w-0">
                  <Select v-model="cond.field" :options="fieldOptions" class="w-full" />
                  <TextInput
                    v-if="cond.field === 'header'"
                    v-model="cond.header_name"
                    placeholder="Header name"
                    class="w-full"
                  />
                </div>
                <Select v-model="cond.operator" :options="operatorOptions" class="w-full" />
                <TextInput
                  v-model="cond.value"
                  :placeholder="placeholder(cond.field)"
                  class="w-full"
                />
                <!-- Conditionless rules are dropped silently; the last one cannot go. -->
                <Button
                  variant="ghost"
                  icon="lucide-x"
                  label="Remove condition"
                  tooltip="Remove condition"
                  :disabled="rule.conditions.length === 1"
                  @click="removeCondition(rule, ci)"
                />
              </div>
            </div>

            <!-- Indented with the conditions so it reads as one more row of them. -->
            <div class="pl-5">
              <Button variant="ghost" icon-left="lucide-plus" @click="addCondition(rule)">
                Add condition
              </Button>
            </div>
          </div>
        </div>

        <div class="relative space-y-1.5 pl-5">
          <!-- -top-4 spans the group gap above so the line is unbroken; the
               extra 0.875rem drops the curve to the middle of this row. -->
          <span
            aria-hidden="true"
            class="absolute left-1 -top-4 h-[1.875rem] w-2.5 border-l border-b rounded-bl-6 border-outline-gray-3"
          />
          <div class="flex flex-wrap items-center gap-2 text-ink-gray-7 text-base">
            <span>Then</span>
            <Select v-model="rule.action" :options="actionOptions" class="w-48" />
            <Button
              class="ml-auto"
              variant="ghost"
              theme="red"
              icon-left="lucide-trash-2"
              @click="promptRemove(rule)"
            >
              Delete rule
            </Button>
          </div>
          <p
            v-if="rule.action === 'skip'"
            class="flex items-start gap-1.5 text-ink-amber-7 text-p-sm"
          >
            <span class="shrink-0 mt-0.5 size-3.5 lucide-triangle-alert" />
            Matching requests bypass the firewall entirely - no managed rules, no inspection.
          </p>
        </div>
        </div>
      </div>
    </div>

    <Dialog v-model="showRemove" :options="{ title: 'Delete rule', size: 'md' }">
      <template #body-content>
        <p class="text-ink-gray-7 text-p-base">
          Delete <strong>{{ removingLabel }}</strong
          >? Requests it was matching fall through to the managed ruleset.
        </p>
        <div class="flex justify-end gap-2 mt-4">
          <Button variant="ghost" @click="showRemove = false">Cancel</Button>
          <Button variant="solid" theme="red" @click="confirmRemove">Delete</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { Badge, Button, Dialog, FormControl, Select, Switch, TextInput } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  ACTION_LABELS,
  FIELD_LABELS,
  OPERATOR_LABELS,
  actionLabel,
  ruleProblem,
  ruleSummary,
} from '@/utils/wafRules'

// Two-way bound so the child owns list edits without mutating a prop.
const rules = defineModel({ type: Array, default: () => [] })
const props = defineProps({
  fields: { type: Array, default: () => [] },
  operators: { type: Array, default: () => [] },
  actions: { type: Array, default: () => [] },
})

const PLACEHOLDERS = {
  source_ip: '10.0.0.0/8, 203.0.113.4',
  method: 'POST',
  uri_path: '/admin',
  host: 'example.com',
}
const MATCH_OPTIONS = [
  { label: 'All', value: 'all' },
  { label: 'Any', value: 'any' },
]

const fieldOptions = computed(() =>
  props.fields.map((f) => ({ label: FIELD_LABELS[f] || f, value: f })),
)
const operatorOptions = computed(() =>
  props.operators.map((o) => ({ label: OPERATOR_LABELS[o] || o, value: o })),
)
const actionOptions = computed(() =>
  props.actions.map((a) => ({ label: ACTION_LABELS[a] || a, value: a })),
)

function placeholder(field) {
  return PLACEHOLDERS[field] || 'value'
}

// Identity-based :key. Index keys re-key rows on delete and Vue patches the
// inputs in place, jumping a focused caret to the wrong row.
const keys = new WeakMap()
let nextKey = 0
function keyOf(object) {
  if (!keys.has(object)) keys.set(object, `k${(nextKey += 1)}`)
  return keys.get(object)
}

// One key, not a set: opening a rule closes the one before it.
const openKey = ref('')
const isOpen = (rule) => openKey.value === keyOf(rule)
function toggleOpen(rule) {
  const key = keyOf(rule)
  openKey.value = openKey.value === key ? '' : key
}

// Same predicate as the save path, so add and save cannot disagree.
const flaggedKey = ref('')
const root = ref(null)
let flagTimer = null

function flagUnfinished() {
  const rule = rules.value.find((candidate) => ruleProblem(candidate))
  if (!rule) return false
  const key = keyOf(rule)
  openKey.value = key
  flaggedKey.value = key
  clearTimeout(flagTimer)
  flagTimer = setTimeout(() => (flaggedKey.value = ''), 900)
  root.value?.querySelector(`[data-rule-key="${key}"]`)?.scrollIntoView({
    block: 'nearest',
    behavior: 'smooth',
  })
  return true
}

onUnmounted(() => clearTimeout(flagTimer))

// Live reorder on dragover; identity keys keep row state through the splice.
const dragKey = ref('')
function onDragStart(rule, event) {
  dragKey.value = keyOf(rule)
  openKey.value = ''
  event.dataTransfer.effectAllowed = 'move'
}
function onDragOver(rule) {
  if (!dragKey.value || dragKey.value === keyOf(rule)) return
  const from = rules.value.findIndex((r) => keyOf(r) === dragKey.value)
  const to = rules.value.findIndex((r) => keyOf(r) === keyOf(rule))
  if (from === -1 || to === -1) return
  const [moved] = rules.value.splice(from, 1)
  rules.value.splice(to, 0, moved)
}
function onDragEnd() {
  dragKey.value = ''
}

function newCondition() {
  return { field: 'uri_path', operator: 'contains', value: '', header_name: '' }
}
function addRule() {
  if (flagUnfinished()) return
  const rule = {
    name: '',
    action: 'block',
    match: 'all',
    enabled: true,
    conditions: [newCondition()],
  }
  rules.value.push(rule)
  // Key the reactive proxy the template iterates, not the raw local object.
  openKey.value = keyOf(rules.value[rules.value.length - 1])
}
function addCondition(rule) {
  rule.conditions.push(newCondition())
}
function removeCondition(rule, index) {
  rule.conditions.splice(index, 1)
}

const showRemove = ref(false)
const removingRule = ref(null)
const removingLabel = computed(() => removingRule.value?.name || 'this rule')
function promptRemove(rule) {
  removingRule.value = rule
  showRemove.value = true
}
function confirmRemove() {
  const index = rules.value.indexOf(removingRule.value)
  if (index !== -1) rules.value.splice(index, 1)
  showRemove.value = false
  removingRule.value = null
}

</script>
