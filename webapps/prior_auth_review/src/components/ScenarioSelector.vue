<script setup lang="ts">
import type { ScenarioOption } from '../Api'

defineProps<{
  options: ScenarioOption[]
  selectedPolicyId: string
}>()

const emit = defineEmits<{
  change: [policyId: string]
}>()
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <p class="eyebrow">Fixture mode</p>
      <h2>Policy scenario</h2>
    </div>
    <label class="field">
      <span>Policy</span>
      <select :value="selectedPolicyId" @change="emit('change', ($event.target as HTMLSelectElement).value)">
        <option v-for="option in options" :key="option.policy_id" :value="option.policy_id">
          {{ option.policy_id }} — {{ option.label }}
        </option>
      </select>
    </label>
    <p class="hint">
      Switch fixture scenarios to test satisfied, blocked, and mixed-review paths.
    </p>
  </section>
</template>
