<script setup lang="ts">
import type { CriterionAnswers, ScenarioOption, Screen1Payload } from '../Api'
import { EaBadge, EaButton, EaSelect } from './ui'
import { labelForCriterionKind } from '../uiLabels'

defineProps<{
  screen1: Screen1Payload | null
  loading: boolean
  screen1Answers: CriterionAnswers
  scenarios: ScenarioOption[]
  selectedPolicyId: string
  subjectIdInput?: string
}>()

const emit = defineEmits<{
  'select-policy': [policyId: string]
  'update-subject-id': [value: string]
  'select-billing-code': [billingCode: string]
  'select-phase': [phase: string]
  'select-cluster': [clusterId: string]
  'answer-guard': [criterionId: string, answer: boolean | null]
  proceed: []
}>()

function normalizeBoolean(value: string) {
  if (value === 'true') return true
  if (value === 'false') return false
  return null
}

const guardAnswerOptions = [
  { value: '__unset__', label: 'Leave unanswered' },
  { value: 'true', label: 'Criterion met' },
  { value: 'false', label: 'Criterion unmet' },
]
</script>

<template>
  <section class="space-y-6" v-if="screen1">
    <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="space-y-2">
        <h1 class="font-serif text-3xl font-semibold text-foreground lg:text-4xl">Select scope</h1>
        <p class="max-w-3xl text-sm text-muted-foreground lg:text-base">
          Confirm the billing code, route branch, and cluster before opening chart-backed review.
        </p>
      </div>
    </header>

    <section class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Current selection</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Scope builder</h2>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <label class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Patient ID</span>
          <EaSelect
            class="w-full"
            :model-value="subjectIdInput ?? undefined"
            :options="screen1.patient_id_options.map((subjectId) => ({ value: subjectId, label: subjectId }))"
            placeholder="Select a patient"
            :disabled="loading"
            @update:model-value="emit('update-subject-id', $event)"
          />
        </label>
        <label class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Policy</span>
          <EaSelect
            class="w-full"
            :model-value="selectedPolicyId"
            :options="scenarios.map((option) => ({ value: option.policy_id, label: `${option.policy_id} — ${option.label}` }))"
            placeholder="Select a policy"
            :disabled="loading"
            @update:model-value="emit('select-policy', $event)"
          />
        </label>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-2">
        <label class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Billing code</span>
          <EaSelect
            class="w-full"
            :model-value="screen1.payload.selection.billing_code ?? undefined"
            :options="screen1.payload.billing_code_options.map((option) => ({ value: option.billing_code, label: option.billing_code }))"
            placeholder="Select a billing code"
            :disabled="loading"
            @update:model-value="emit('select-billing-code', $event)"
          />
        </label>

        <label
          v-if="screen1.payload.phase_options.length > 0 || screen1.payload.selection.selected_phase"
          class="grid gap-2"
        >
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Phase</span>
          <EaSelect
            class="w-full"
            :model-value="screen1.payload.selection.selected_phase ?? undefined"
            :options="screen1.payload.phase_options.map((option) => ({ value: option.value, label: option.label }))"
            placeholder="Select a phase"
            :disabled="loading || screen1.payload.phase_options.length === 0"
            @update:model-value="emit('select-phase', $event)"
          />
        </label>
      </div>

      <div class="mt-4 grid gap-2" v-if="screen1.payload.cluster_options.length">
        <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Cluster</span>
        <EaSelect
          class="w-full"
          :model-value="screen1.payload.selection.selected_cluster_id ?? undefined"
          :options="screen1.payload.cluster_options.map((option) => ({ value: option.cluster_id, label: option.cluster_label }))"
          placeholder="Select a clinical cluster"
          :disabled="loading"
          @update:model-value="emit('select-cluster', $event)"
        />
      </div>

      <div
        v-if="screen1.payload.route_display.route_label"
        class="mt-6 rounded-[1.5rem] border border-border bg-background px-5 py-4"
      >
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Matched route</p>
        <p class="mt-2 font-serif text-2xl font-semibold text-foreground">{{ screen1.payload.route_display.route_label }}</p>
        <p class="mt-1 font-mono text-xs text-muted-foreground">{{ screen1.payload.route_display.route_id }}</p>
      </div>
    </section>

    <section
      v-if="screen1.payload.route_guard_questions.length || screen1.payload.cluster_entry_guard_questions.length"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Clinician questions</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Guard questions</h2>
      </div>

      <div class="grid gap-4">
        <article
          v-for="question in [...screen1.payload.route_guard_questions, ...screen1.payload.cluster_entry_guard_questions]"
          :key="question.criterion_id"
          class="grid gap-4 rounded-[1.5rem] border border-border bg-background p-5"
        >
          <div class="flex flex-wrap items-center gap-2">
            <EaBadge :tone="question.criterion_kind === 'route_guard' ? 'route' : 'entry'">
              {{ labelForCriterionKind(question.criterion_kind) }}
            </EaBadge>
            <EaBadge v-if="question.required" tone="neutral">Required</EaBadge>
          </div>
          <h3 class="font-serif text-xl font-semibold text-foreground">{{ question.prompt }}</h3>
          <label class="grid gap-2">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Answer</span>
            <EaSelect
              class="w-full sm:max-w-xs"
              :model-value="screen1Answers[question.criterion_id]?.answer === null || screen1Answers[question.criterion_id]?.answer === undefined ? '__unset__' : String(screen1Answers[question.criterion_id]?.answer)"
              :options="guardAnswerOptions"
              placeholder="Leave unanswered"
              :disabled="loading"
              @update:model-value="emit('answer-guard', question.criterion_id, normalizeBoolean($event))"
            />
          </label>
        </article>
      </div>
    </section>

    <div class="sticky bottom-3 z-10 mt-2">
      <div class="grid gap-3 rounded-[1.5rem] border border-border bg-background/95 p-4 shadow-[0_16px_30px_rgba(26,26,26,0.08)] backdrop-blur">
        <div
          v-if="loading"
          class="flex items-start gap-3 rounded-[1.25rem] border border-border bg-card px-4 py-3"
          aria-live="polite"
        >
          <span class="loading-spinner" aria-hidden="true" />
          <div class="grid gap-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Preparing next step</span>
            <p class="text-sm text-muted-foreground">Building the eligibility review from the current scope selection.</p>
          </div>
        </div>
        <EaButton
          variant="accent"
          size="lg"
          class="w-full justify-center sm:w-auto"
          :disabled="loading || !subjectIdInput || screen1.payload.next_action !== 'proceed_screen_2'"
          @click="emit('proceed')"
        >
          {{ loading ? 'Preparing eligibility review...' : 'Continue to eligibility review' }}
        </EaButton>
      </div>
    </div>
  </section>
</template>
