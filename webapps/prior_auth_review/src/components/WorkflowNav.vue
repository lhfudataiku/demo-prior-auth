<script setup lang="ts">
defineProps<{
  currentPage: 'screen1' | 'screen2' | 'screen3'
  screen2Ready: boolean
  screen3Ready: boolean
}>()

const emit = defineEmits<{
  navigate: [page: 'screen1' | 'screen2' | 'screen3']
}>()

const steps = [
  { id: 'screen1', label: 'Step 1', title: 'Select scope', enabled: true },
  { id: 'screen2', label: 'Step 2', title: 'Review criteria', enabled: true },
  { id: 'screen3', label: 'Step 3', title: 'Review summary', enabled: true },
] as const
</script>

<template>
  <nav class="workflow-steps panel">
    <div class="section-header">
      <p class="eyebrow">Workflow</p>
      <h2>Review steps</h2>
    </div>
    <div class="workflow-steps-track">
      <button
        v-for="(step, index) in steps"
        :key="step.id"
        class="workflow-step-dot"
        :data-active="currentPage === step.id"
        :disabled="(step.id === 'screen2' && !screen2Ready) || (step.id === 'screen3' && !screen3Ready)"
        @click="emit('navigate', step.id)"
      >
        <span class="workflow-step-index">{{ index + 1 }}</span>
        <span class="workflow-step-copy">
          <span class="workflow-step-label">{{ step.label }}</span>
          <strong>{{ step.title }}</strong>
        </span>
      </button>
    </div>
  </nav>
</template>
