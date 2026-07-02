<script setup lang="ts">
import { EaBadge } from './ui'

defineProps<{
  currentPage: 'screen1' | 'screen2' | 'screen3'
  screen2Ready: boolean
  screen3Ready: boolean
}>()

const emit = defineEmits<{
  navigate: [page: 'screen1' | 'screen2' | 'screen3']
}>()

const steps = [
  { id: 'screen1', title: 'Select scope', enabled: true },
  { id: 'screen2', title: 'Review eligibility', enabled: true },
  { id: 'screen3', title: 'Review submission', enabled: true },
] as const
</script>

<template>
  <nav class="mb-6 rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
    <div class="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div class="space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Workflow</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Review steps</h2>
      </div>
      <EaBadge tone="neutral">
        {{ currentPage === 'screen1' ? 'Scope selection' : currentPage === 'screen2' ? 'Eligibility review' : 'Final review' }}
      </EaBadge>
    </div>
    <div class="grid gap-4 lg:grid-cols-3">
      <button
        v-for="(step, index) in steps"
        :key="step.id"
        class="relative flex items-start gap-4 rounded-[1.25rem] border p-4 text-left transition-colors"
        :disabled="(step.id === 'screen2' && !screen2Ready) || (step.id === 'screen3' && !screen3Ready)"
        :class="currentPage === step.id
          ? 'border-primary bg-background shadow-sm'
          : 'border-border bg-background hover:bg-accent/40 disabled:hover:bg-background'"
        @click="emit('navigate', step.id)"
      >
        <span
          class="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border font-mono text-base"
          :class="currentPage === step.id
            ? 'border-primary bg-primary text-primary-foreground shadow-sm'
            : 'border-border bg-card text-muted-foreground'"
        >
          {{ index + 1 }}
        </span>
        <span class="grid gap-1">
          <strong class="font-serif text-lg font-semibold text-foreground">{{ step.title }}</strong>
          <span class="text-sm text-muted-foreground">
            {{ step.id === 'screen1'
              ? 'Resolve the policy route and clinical scope.'
              : step.id === 'screen2'
                ? 'Compare chart evidence with clinician judgment.'
                : 'Review the deterministic submission package.' }}
          </span>
        </span>
      </button>
    </div>
  </nav>
</template>
