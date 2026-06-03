<script setup lang="ts">
import { computed } from 'vue'
import type { AgentRunProgress, CriterionAnswers, CriterionRow, LogicEvaluation, Screen2Payload } from '../Api'
import CriterionCard from './CriterionCard.vue'
import { humanizeToken, labelForCriterionState, toneForStatus } from '../uiLabels'

const props = defineProps<{
  screen2: Screen2Payload | null
  criteria: CriterionRow[]
  criteriaCount: number | null
  editedAnswers: CriterionAnswers
  logicEvaluation: LogicEvaluation | null
  answerOrigins: Record<string, 'screen1' | 'screen2'>
  submitting: boolean
  dataSource: 'local' | 'dss'
  agentStatus: 'running' | 'hitl_paused' | 'completed' | 'failed' | null
  agentMessage: string | null
  agentEvents: Array<Record<string, unknown>>
  agentProgress: AgentRunProgress | null
}>()

const emit = defineEmits<{
  answer: [criterionId: string, value: boolean | null]
  comment: [criterionId: string, value: string]
  submit: []
}>()

const progressPercent = computed(() => {
  const total = props.agentProgress?.total_criteria
  const completed = props.agentProgress?.completed_criteria ?? 0
  if (!total || total <= 0) return null
  return Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
})

const canEdit = computed(() =>
  props.dataSource === 'local' || props.agentStatus === 'hitl_paused' || props.agentStatus === null,
)

const showCriteria = computed(() =>
  props.criteria.length > 0,
)

const reviewProgressTitle = computed(() => {
  if (props.submitting) return 'Preparing final review'
  if (props.agentStatus === 'failed') return 'Review interrupted'
  if (props.agentStatus === 'hitl_paused') return 'Review ready'
  if (props.agentStatus === 'completed') return 'Review complete'
  if (props.agentStatus === 'running') return 'Preparing review'
  if (props.logicEvaluation) return 'Review ready'
  return 'Preparing review'
})

const reviewProgressBody = computed(() => {
  if (props.submitting) return 'We are finalizing the clinician-approved review and preparing the submission summary.'
  if (props.agentStatus === 'failed') return 'The agent run failed before the review could be completed.'
  if (props.agentStatus === 'hitl_paused') return 'Chart evidence is hydrated and the review is ready for clinician confirmation.'
  if (props.agentStatus === 'completed') return 'The reviewed output has been finalized successfully.'
  if (props.agentStatus === 'running') {
    if (props.agentProgress?.current_criterion_prompt) return props.agentProgress.current_criterion_prompt
    return 'The Structured Agent is reviewing chart evidence and preparing the eligibility review.'
  }
  if (props.logicEvaluation) return 'Resolve any remaining issues, then continue to the final submission review.'
  return 'The backend is still rendering the review content.'
})

const progressSummary = computed(() => {
  const total = props.agentProgress?.total_criteria ?? props.criteriaCount
  const completed = props.agentProgress?.completed_criteria ?? 0
  if (typeof total !== 'number' || total <= 0) return 'Rendering criteria'
  if (props.agentStatus === 'hitl_paused' || props.logicEvaluation) return `${total} criteria ready for review`
  return `${completed} of ${total} criteria reviewed`
})

const showReviewProgress = computed(() =>
  !!props.agentStatus || props.submitting || (!props.logicEvaluation && props.criteriaCount !== null),
)

const showActionLoading = computed(() =>
  props.submitting || props.agentStatus === 'running',
)

const actionButtonLabel = computed(() =>
  props.submitting ? 'Preparing final review...' : 'Continue to final review',
)
</script>

<template>
  <section class="page-stack" v-if="screen2 || agentStatus || criteria.length">
    <header class="page-header">
      <div>
        <h1>Eligibility review</h1>
        <p class="hero-copy">
          Compare chart evidence with clinician input, resolve disagreements, and prepare the final summary.
        </p>
      </div>
      <div class="header-actions">
        <div class="status-kv">
          <span class="label">Review stage</span>
          <span class="status-chip" :data-tone="toneForStatus(agentStatus || screen2?.status || 'running')">
            {{ reviewProgressTitle }}
          </span>
        </div>
      </div>
    </header>

    <section class="panel" v-if="showReviewProgress">
      <div class="section-header">
        <p class="eyebrow">Structured agent</p>
        <h2>Review progress</h2>
      </div>
      <div class="progress-hero">
        <span v-if="agentStatus === 'running' || submitting" class="loading-spinner" aria-hidden="true" />
        <div class="progress-hero-copy">
          <p class="body-copy">{{ reviewProgressBody }}</p>
          <p v-if="agentMessage" class="summary-meta">{{ agentMessage }}</p>
        </div>
      </div>
      <div v-if="agentProgress" class="status-bar streaming-status">
        <div class="status-item" v-if="agentProgress.total_criteria !== null">
          <span class="label">Queue</span>
          <span class="status-chip" data-tone="neutral">
            {{ agentProgress.completed_criteria }} / {{ agentProgress.total_criteria }}
          </span>
        </div>
        <div class="status-item" v-if="agentProgress.current_criterion_id">
          <span class="label">Current criterion</span>
          <span class="status-chip" data-tone="neutral">{{ agentProgress.current_criterion_id }}</span>
        </div>
        <div class="status-item" v-if="agentProgress.current_block_id">
          <span class="label">Current block</span>
          <span class="status-chip" data-tone="neutral">{{ agentProgress.current_block_id }}</span>
        </div>
      </div>
      <div v-if="progressPercent !== null" class="progress-meter" aria-hidden="true">
        <div class="progress-meter__fill" :style="{ width: `${progressPercent}%` }" />
      </div>
      <details class="evidence-panel" v-if="agentEvents.length || agentProgress?.current_block_id">
        <summary>Agent details</summary>
        <div class="summary-stack">
          <p v-if="agentProgress?.current_block_id" class="summary-meta">Current block: {{ agentProgress.current_block_id }}</p>
          <p v-if="agentEvents.length" class="summary-meta">Events captured: {{ agentEvents.length }}</p>
        </div>
      </details>
    </section>

    <section class="status-bar panel" v-if="logicEvaluation || criteriaCount !== null">
      <div class="status-item">
        <span class="label">Cluster status</span>
        <span class="status-chip" :data-tone="toneForStatus(logicEvaluation?.selected_cluster_status || 'running')">
          {{ logicEvaluation ? labelForCriterionState(logicEvaluation.selected_cluster_status) : humanizeToken(agentStatus || 'running') }}
        </span>
      </div>
      <div class="status-item">
        <span class="label">Review progress</span>
        <span class="status-chip status-chip--loading" :data-tone="toneForStatus(agentStatus || (logicEvaluation ? 'ok' : 'running'))">
          <span v-if="agentStatus === 'running' || submitting" class="loading-spinner loading-spinner--inline" aria-hidden="true" />
          {{ progressSummary }}
        </span>
      </div>
      <div class="status-item">
        <span class="label">Criteria count</span>
        <span class="detail-chip" >{{ criteriaCount ?? '—' }}</span>
      </div>
      <div class="status-item">
        <span class="label">Satisfied</span>
        <span class="status-chip" data-tone="positive">{{ logicEvaluation?.criterion_counts.satisfied ?? '—' }}</span>
      </div>
      <div class="status-item">
        <span class="label">Not satisfied</span>
        <span class="status-chip" data-tone="warning">{{ logicEvaluation?.criterion_counts.not_satisfied ?? '—' }}</span>
      </div>
      <div class="status-item">
        <span class="label">Unresolved</span>
        <span class="status-chip" data-tone="neutral">{{ logicEvaluation?.criterion_counts.unresolved ?? '—' }}</span>
      </div>
    </section>

    <section class="criteria-stack" v-if="showCriteria">
      <CriterionCard
        v-for="criterion in criteria"
        :key="criterion.criterion_id"
        :criterion="criterion"
        :answer="editedAnswers[criterion.criterion_id]"
        :origin="answerOrigins[criterion.criterion_id]"
        :readonly="!canEdit"
        :loading="dataSource === 'dss' && !screen2"
        @answer="(criterionId, value) => emit('answer', criterionId, value)"
        @comment="(criterionId, value) => emit('comment', criterionId, value)"
      />
    </section>

    <div class="page-actions" v-if="screen2 && canEdit">
      <div v-if="showActionLoading" class="cta-status" aria-live="polite">
        <span class="loading-spinner" aria-hidden="true" />
        <div class="cta-status-copy">
          <span class="label">Preparing next step</span>
          <p class="summary-meta">
            {{ submitting
              ? 'Building the final submission review from the approved answers.'
              : 'The backend is still hydrating the review before you can continue.' }}
          </p>
        </div>
      </div>
      <button
        class="primary-button"
        :disabled="submitting || agentStatus === 'running'"
        @click="emit('submit')"
      >
        {{ actionButtonLabel }}
      </button>
    </div>
  </section>
</template>
