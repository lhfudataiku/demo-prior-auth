<script setup lang="ts">
import { computed } from 'vue'
import type { AgentRunProgress, CriterionAnswers, CriterionRow, LogicEvaluation, Screen2Payload } from '../Api'
import CriterionCard from './CriterionCard.vue'

function toneForOutcome(value: string) {
  if (['satisfied', 'found', 'ok', 'approved', 'proceed_screen_3'].includes(value)) return 'positive'
  if (['not_satisfied', 'conflict', 'warning', 'ambiguous'].includes(value)) return 'warning'
  if (['unresolved', 'needs_clinician', 'unanswered', 'stay_screen_2'].includes(value)) return 'neutral'
  return value
}

const props = defineProps<{
  screen2: Screen2Payload | null
  criteria: CriterionRow[]
  editedAnswers: CriterionAnswers
  logicEvaluation: LogicEvaluation | null
  nextAction: string
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
</script>

<template>
  <section class="page-stack" v-if="screen2 || agentStatus">
    <header class="page-header">
      <div>
        <h1>Criterion review</h1>
        <p class="hero-copy">
          Compare chart evidence with clinician input, resolve disagreements, and prepare the final summary.
        </p>
      </div>
      <div class="header-actions">
        <div class="status-kv">
          <span class="label">Agent</span>
          <span class="status-chip" :data-tone="toneForOutcome(agentStatus || screen2?.status || 'running')">
            {{ agentStatus || screen2?.status }}
          </span>
        </div>
        <button
          v-if="screen2 && (dataSource === 'local' || agentStatus === 'hitl_paused')"
          class="primary-button"
          :disabled="submitting"
          @click="emit('submit')"
        >
          {{ submitting ? 'Submitting...' : 'Submit review' }}
        </button>
      </div>
    </header>

    <section class="panel" v-if="agentStatus">
      <div class="section-header">
        <p class="eyebrow">Structured agent</p>
        <h2>Workflow status</h2>
      </div>
      <p v-if="agentStatus === 'running'">The Structured Agent is running and streaming workflow progress.</p>
      <p v-else-if="agentStatus === 'hitl_paused'">The agent is paused at the required human-validation step.</p>
      <p v-else-if="agentStatus === 'completed'">The agent completed successfully.</p>
      <p v-else-if="agentStatus === 'failed'">The agent run failed.</p>
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
      <p v-if="agentProgress?.current_criterion_prompt" class="summary-meta">
        {{ agentProgress.current_criterion_prompt }}
      </p>
      <p v-if="agentMessage" class="summary-meta">{{ agentMessage }}</p>
      <p class="summary-meta" v-if="agentEvents.length">Events captured: {{ agentEvents.length }}</p>
    </section>

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

    <section class="criteria-stack" v-if="screen2">
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
