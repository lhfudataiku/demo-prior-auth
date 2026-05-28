<script setup lang="ts">
import type { CriterionAnswers, CriterionRow, LogicEvaluation, Screen2Payload } from '../Api'
import CriterionCard from './CriterionCard.vue'

function toneForOutcome(value: string) {
  if (['satisfied', 'found', 'ok', 'approved', 'proceed_screen_3'].includes(value)) return 'positive'
  if (['not_satisfied', 'conflict', 'warning', 'ambiguous'].includes(value)) return 'warning'
  if (['unresolved', 'needs_clinician', 'unanswered', 'stay_screen_2'].includes(value)) return 'neutral'
  return value
}

defineProps<{
  screen2: Screen2Payload | null
  criteria: CriterionRow[]
  editedAnswers: CriterionAnswers
  logicEvaluation: LogicEvaluation | null
  nextAction: string
  answerOrigins: Record<string, 'screen1' | 'screen2'>
  submitting: boolean
}>()

const emit = defineEmits<{
  answer: [criterionId: string, value: boolean | null]
  comment: [criterionId: string, value: string]
  submit: []
}>()
</script>

<template>
  <section class="page-stack" v-if="screen2">
    <header class="page-header">
      <div>
        <h1>Criterion review</h1>
        <p class="hero-copy">
          Compare chart evidence with clinician input, resolve disagreements, and prepare the final summary.
        </p>
      </div>
      <div class="header-actions">
        <div class="status-kv">
          <span class="label">Status</span>
          <span class="status-chip" :data-tone="toneForOutcome(screen2.status)">{{ screen2.status }}</span>
        </div>
        <button class="primary-button" :disabled="submitting" @click="emit('submit')">
          {{ submitting ? 'Submitting...' : 'Submit review' }}
        </button>
      </div>
    </header>

    <section class="status-bar panel" v-if="logicEvaluation">
      <div class="status-item">
        <span class="label">Cluster status</span>
        <span class="status-chip" :data-tone="toneForOutcome(logicEvaluation.selected_cluster_status)">
          {{ logicEvaluation.selected_cluster_status }}
        </span>
      </div>
      <div class="status-item">
        <span class="label">Next action</span>
        <span class="status-chip" :data-tone="toneForOutcome(nextAction)">
          {{ nextAction }}
        </span>
      </div>
      <div class="status-item">
        <span class="label">Satisfied</span>
        <span class="status-chip" data-tone="positive">{{ logicEvaluation.criterion_counts.satisfied }}</span>
      </div>
      <div class="status-item">
        <span class="label">Not satisfied</span>
        <span class="status-chip" data-tone="warning">{{ logicEvaluation.criterion_counts.not_satisfied }}</span>
      </div>
      <div class="status-item">
        <span class="label">Unresolved</span>
        <span class="status-chip" data-tone="neutral">{{ logicEvaluation.criterion_counts.unresolved }}</span>
      </div>
    </section>

    <section class="criteria-stack">
      <CriterionCard
        v-for="criterion in criteria"
        :key="criterion.criterion_id"
        :criterion="criterion"
        :answer="editedAnswers[criterion.criterion_id]"
        :origin="answerOrigins[criterion.criterion_id]"
        @answer="(criterionId, value) => emit('answer', criterionId, value)"
        @comment="(criterionId, value) => emit('comment', criterionId, value)"
      />
    </section>
  </section>
</template>
