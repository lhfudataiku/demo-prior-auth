<script setup lang="ts">
import type { ScenarioOption } from '../Api'
import { EaSelect } from './ui'

defineProps<{
  options: ScenarioOption[]
  selectedPolicyId: string
}>()

const emit = defineEmits<{
  change: [policyId: string]
}>()
</script>

<template>
  <section class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
    <div class="mb-4 space-y-1">
      <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Fixture mode</p>
      <h2 class="font-serif text-2xl font-semibold text-foreground">Policy scenario</h2>
    </div>
    <label class="grid gap-2">
      <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Policy</span>
      <EaSelect
        :model-value="selectedPolicyId"
        :options="options.map((option) => ({ value: option.policy_id, label: `${option.policy_id} — ${option.label}` }))"
        placeholder="Select a policy"
        @update:model-value="emit('change', $event)"
      />
    </label>
    <p class="mt-3 text-sm text-muted-foreground">
      Switch fixture scenarios to test satisfied, blocked, and mixed-review paths.
    </p>
  </section>
</template>
