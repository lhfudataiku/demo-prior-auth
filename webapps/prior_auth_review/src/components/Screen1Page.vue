<script setup lang="ts">
import type { CriterionAnswers, ScenarioOption, Screen1Payload } from '../Api'

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
</script>

<template>
  <section class="page-stack" v-if="screen1">
    <header class="page-header">
      <div>
        <p class="eyebrow">Screen 1</p>
        <h1>Select route and scope</h1>
        <p class="hero-copy">
          Confirm the billing code, route branch, and cluster before opening chart-backed review.
        </p>
      </div>
      <span class="status-chip" data-tone="needs_clinician">{{ screen1.payload.step.replaceAll('_', ' ') }}</span>
    </header>

    <section class="panel">
      <div class="section-header">
        <p class="eyebrow">Current selection</p>
        <h2>Scope builder</h2>
      </div>

      <div class="field-row">
        <label class="field">
          <span>Patient ID</span>
          <select
            :value="subjectIdInput ?? ''"
            @change="emit('update-subject-id', ($event.target as HTMLSelectElement).value)"
          >
            <option value="">Select a patient</option>
            <option v-for="subjectId in screen1.patient_id_options" :key="subjectId" :value="subjectId">
              {{ subjectId }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>Policy</span>
          <select :value="selectedPolicyId" @change="emit('select-policy', ($event.target as HTMLSelectElement).value)">
            <option v-for="option in scenarios" :key="option.policy_id" :value="option.policy_id">
              {{ option.policy_id }} — {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="field-row">
        <label class="field">
          <span>Billing code</span>
          <select
            :value="screen1.payload.selection.billing_code ?? ''"
            @change="emit('select-billing-code', ($event.target as HTMLSelectElement).value)"
          >
            <!-- TODO: Replace these placeholder billing-code labels with policy_master_v4.billing_code_sets labels. -->
            <option
              v-for="option in screen1.payload.billing_code_options"
              :key="option.billing_code"
              :value="option.billing_code"
            >
              {{ option.billing_code }}
            </option>
          </select>
        </label>

        <label class="field" v-if="screen1.payload.phase_options.length > 0 || screen1.payload.selection.selected_phase">
          <span>Phase</span>
          <select
            :value="screen1.payload.selection.selected_phase ?? ''"
            :disabled="screen1.payload.phase_options.length === 0"
            @change="emit('select-phase', ($event.target as HTMLSelectElement).value)"
          >
            <option value="">Select a phase</option>
            <option v-for="option in screen1.payload.phase_options" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="field" v-if="screen1.payload.cluster_options.length">
        <span>Cluster</span>
        <select
          :value="screen1.payload.selection.selected_cluster_id ?? ''"
          @change="emit('select-cluster', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">Select a clinical cluster</option>
          <option v-for="option in screen1.payload.cluster_options" :key="option.cluster_id" :value="option.cluster_id">
            {{ option.cluster_label }}
          </option>
        </select>
      </div>

      <div class="scope-preview" v-if="screen1.payload.route_display.route_label">
        <p class="label">Matched route</p>
        <p class="result-headline">{{ screen1.payload.route_display.route_label }}</p>
        <p class="summary-meta">{{ screen1.payload.route_display.route_id }}</p>
      </div>
    </section>

    <section
      v-if="screen1.payload.route_guard_questions.length || screen1.payload.cluster_entry_guard_questions.length"
      class="panel"
    >
      <div class="section-header">
        <p class="eyebrow">Clinician questions</p>
        <h2>Guard questions</h2>
      </div>

      <div class="guard-stack">
        <article
          v-for="question in [...screen1.payload.route_guard_questions, ...screen1.payload.cluster_entry_guard_questions]"
          :key="question.criterion_id"
          class="guard-card"
        >
          <div class="chip-row">
            <span class="kind-badge">{{ question.criterion_kind.replaceAll('_', ' ') }}</span>
            <span v-if="question.required" class="detail-chip">Required</span>
          </div>
          <h3>{{ question.prompt }}</h3>
          <label class="field">
            <span>Answer</span>
            <select
              :value="screen1Answers[question.criterion_id]?.answer === null || screen1Answers[question.criterion_id]?.answer === undefined ? '' : String(screen1Answers[question.criterion_id]?.answer)"
              @change="emit('answer-guard', question.criterion_id, normalizeBoolean(($event.target as HTMLSelectElement).value))"
            >
              <option value="">Leave unanswered</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
        </article>
      </div>
    </section>

    <div class="page-actions">
      <button
        class="primary-button"
        :disabled="loading || !subjectIdInput || screen1.payload.next_action !== 'proceed_screen_2'"
        @click="emit('proceed')"
      >
        {{ loading ? 'Loading...' : 'Open Screen 2 review' }}
      </button>
    </div>
  </section>
</template>
