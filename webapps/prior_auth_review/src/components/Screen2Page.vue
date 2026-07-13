<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import type { AgentRunProgress, CriterionAnswers, CriterionRow, LogicEvaluation, Screen2Payload } from '../Api'
import CriterionCard from './CriterionCard.vue'
import { EaBadge, EaButton, EaEmpty, EaInfo } from './ui'
import { humanizeToken, labelForCriterionState } from '../uiLabels'

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
  focusedCriterionId: string | null
}>()

const emit = defineEmits<{
  answer: [criterionId: string, value: boolean | null]
  comment: [criterionId: string, value: string]
  'clear-focus': []
  submit: []
}>()

function labelForAgentPhase(blockId: string | null | undefined) {
  switch (blockId) {
    case 'init_state':
    case 'plan_retrieval':
      return 'Preparing the review'
    case 'execute_plan':
    case 'reason_one_criterion':
      return 'Gathering chart evidence'
    case 'accumulate_result':
    case 'build_criterion_ui_map':
      return 'Preparing criteria for review'
    case 'evaluate_logic_tree':
      return 'Analyzing chart evidence'
    case 'prepare_screen_2_review_payload':
      return 'Building the eligibility review'
    case 'request_screen_2_human_review':
      return 'Review ready'
    case 'emit_review_result_artifact':
      return 'Preparing final review'
    default:
      return null
  }
}

const progressPercent = computed(() => {
  const total = props.agentProgress?.total_criteria
  const completed = props.agentProgress?.completed_criteria ?? 0
  if (!total || total <= 0) return null
  return Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
})

const canEdit = computed(() =>
  props.dataSource === 'local'
    || props.agentStatus === 'hitl_paused'
    || props.agentStatus === 'completed'
    || props.agentStatus === null,
)

const showCriteria = computed(() => props.criteria.length > 0)
const agentPhaseLabel = computed(() => labelForAgentPhase(props.agentProgress?.current_block_id))

const reviewProgressTitle = computed(() => {
  if (props.submitting) return 'Preparing final review'
  if (props.agentStatus === 'failed') return 'Review interrupted'
  if (props.agentStatus === 'hitl_paused') return 'Review ready'
  if (props.agentStatus === 'completed') return 'Review complete'
  if (props.agentStatus === 'running') return 'Review in progress'
  if (props.logicEvaluation) return 'Review ready'
  return 'Preparing the review'
})

const reviewProgressBody = computed(() => {
  if (props.submitting) return 'We are finalizing the clinician-approved review and preparing the submission summary.'
  if (props.agentStatus === 'failed') return 'The agent run failed before the review could be completed.'
  if (props.agentStatus === 'hitl_paused') return 'The eligibility review is ready for clinician confirmation.'
  if (props.agentStatus === 'completed') return 'The reviewed output has been finalized successfully.'
  if (props.agentStatus === 'running') {
    return 'Comparing chart evidence against each policy criterion.'
  }
  if (props.logicEvaluation) return 'Resolve any remaining issues, then continue to the final submission review.'
  return 'Preparing the review.'
})

// Surfaces the clinician-facing agent phase (labelForAgentPhase) as the panel
// heading while running; falls back to the high-level stage title otherwise.
const reviewProgressHeading = computed(() => {
  if (props.agentStatus === 'running' && agentPhaseLabel.value) return agentPhaseLabel.value
  return reviewProgressTitle.value
})

const progressSummary = computed(() => {
  const total = props.agentProgress?.total_criteria ?? props.criteriaCount
  const completed = props.agentProgress?.completed_criteria ?? 0
  if (typeof total !== 'number' || total <= 0) return 'Preparing criteria for review'
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

const isSubmitReady = computed(() =>
  !!props.screen2 && canEdit.value && props.agentStatus !== 'running' && !props.submitting,
)

watch(
  () => [props.focusedCriterionId, props.criteria.length] as const,
  async ([criterionId]) => {
    if (!criterionId) return
    await nextTick()
    const target = document.getElementById(`criterion-${criterionId}`)
    if (!(target instanceof HTMLElement)) return
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    target.classList.remove('criterion-card--focused')
    void target.offsetWidth
    target.classList.add('criterion-card--focused')
    window.setTimeout(() => {
      target.classList.remove('criterion-card--focused')
    }, 2200)
    emit('clear-focus')
  },
  { immediate: true },
)
</script>

<template>
  <section v-if="screen2 || agentStatus || criteria.length" class="space-y-6">
    <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="space-y-2">
        <h1 class="font-serif text-3xl font-semibold text-foreground lg:text-4xl">Eligibility review</h1>
        <p class="max-w-3xl text-sm text-muted-foreground lg:text-base">
          Compare chart evidence with clinician input, resolve disagreements, and prepare the final summary.
        </p>
      </div>
      <div class="grid gap-2">
        <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
          Review stage
          <EaInfo>Where this case sits in the automated eligibility review, from preparation through clinician confirmation.</EaInfo>
        </span>
        <p class="font-serif text-3xl font-semibold text-foreground">{{ reviewProgressTitle }}</p>
      </div>
    </header>

    <section
      v-if="showReviewProgress"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div class="space-y-1">
          <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Structured agent</p>
          <h2 class="font-serif text-2xl font-semibold text-foreground">Review progress</h2>
        </div>
        <EaBadge tone="neutral">
          {{ progressSummary }}
        </EaBadge>
      </div>

      <div class="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.9fr)]">
        <div class="flex flex-col justify-between gap-6 rounded-[1.5rem] border border-border bg-background px-6 py-5">
          <div class="flex items-start gap-3">
            <span
              v-if="agentStatus === 'running' || submitting"
              class="loading-spinner mt-1"
              aria-hidden="true"
            />
            <div class="grid gap-1.5">
              <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
                {{ agentStatus === 'running' ? 'Current phase' : 'Review status' }}
              </span>
              <p class="font-serif text-2xl font-semibold text-foreground">{{ reviewProgressHeading }}</p>
              <p class="text-sm text-muted-foreground">{{ reviewProgressBody }}</p>
              <p v-if="agentMessage" class="font-mono text-xs text-muted-foreground">{{ agentMessage }}</p>
            </div>
          </div>

          <div class="grid gap-2">
            <div class="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.04em] text-muted-foreground">
              <span>{{ progressSummary }}</span>
              <span v-if="progressPercent !== null">{{ progressPercent }}%</span>
            </div>
            <div class="h-2.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
              <div
                class="h-full rounded-full bg-[linear-gradient(90deg,var(--dk-green),var(--dk-dark-green))] transition-[width] duration-200"
                :class="{ 'progress-indeterminate': progressPercent === null && (agentStatus === 'running' || submitting) }"
                :style="progressPercent !== null ? { width: `${progressPercent}%` } : undefined"
              />
            </div>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          <div class="rounded-[1.5rem] border border-border bg-background px-4 py-4">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Runtime</span>
            <p class="mt-2 font-serif text-xl font-semibold text-foreground">
              {{ dataSource === 'dss' ? 'Live Structured Agent' : 'Fixture-backed review' }}
            </p>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ dataSource === 'dss'
                ? 'Managed chart review with clinician confirmation.'
                : 'Deterministic local artifact path for iterative frontend work.' }}
            </p>
          </div>

          <div
            v-if="agentProgress"
            class="rounded-[1.5rem] border border-border bg-background px-4 py-4"
          >
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Queue detail</span>
            <div class="mt-3 grid gap-3">
              <div v-if="agentProgress.total_criteria !== null" class="grid gap-1">
                <span class="font-mono text-[11px] uppercase tracking-[0.04em] text-muted-foreground">Criteria</span>
                <p class="text-sm text-foreground">
                  {{ agentProgress.completed_criteria }} / {{ agentProgress.total_criteria }}
                </p>
              </div>
              <div v-if="agentProgress.current_criterion_id" class="grid gap-1">
                <span class="font-mono text-[11px] uppercase tracking-[0.04em] text-muted-foreground">Current criterion</span>
                <p class="font-mono text-xs text-foreground">{{ agentProgress.current_criterion_id }}</p>
              </div>
              <div v-if="agentEvents.length" class="grid gap-1">
                <span class="font-mono text-[11px] uppercase tracking-[0.04em] text-muted-foreground">Events captured</span>
                <p class="text-sm text-foreground">{{ agentEvents.length }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="logicEvaluation || criteriaCount !== null"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-1">
          <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Outcome</p>
          <h2 class="font-serif text-2xl font-semibold text-foreground">Eligibility summary</h2>
        </div>
        <div class="grid gap-2">
          <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Cluster status
            <EaInfo>Overall eligibility of the selected diagnosis cluster after combining all its criteria through the policy logic tree.</EaInfo>
          </span>
          <p class="font-serif text-3xl font-semibold text-foreground">
            {{ logicEvaluation ? labelForCriterionState(logicEvaluation.selected_cluster_status) : humanizeToken(agentStatus || 'running') }}
          </p>
        </div>
      </div>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Criteria count
            <EaInfo>Total number of policy criteria evaluated for this cluster.</EaInfo>
          </span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">{{ criteriaCount ?? '—' }}</p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Satisfied
            <EaInfo>Criteria met by chart evidence or confirmed by the clinician.</EaInfo>
          </span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ logicEvaluation?.criterion_counts.satisfied ?? '—' }}
          </p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Not satisfied
            <EaInfo>Criteria the chart evidence did not meet.</EaInfo>
          </span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ logicEvaluation?.criterion_counts.not_satisfied ?? '—' }}
          </p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Unresolved
            <EaInfo>Criteria still needing clinician input before the review can be finalized.</EaInfo>
          </span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ logicEvaluation?.criterion_counts.unresolved ?? '—' }}
          </p>
        </div>
      </div>
    </section>

    <section v-if="showCriteria" class="grid gap-4">
      <CriterionCard
        v-for="criterion in criteria"
        :key="criterion.criterion_id"
        :id="`criterion-${criterion.criterion_id}`"
        :criterion="criterion"
        :answer="editedAnswers[criterion.criterion_id]"
        :origin="answerOrigins[criterion.criterion_id]"
        :readonly="!canEdit"
        :loading="dataSource === 'dss' && !screen2"
        @answer="(criterionId, value) => emit('answer', criterionId, value)"
        @comment="(criterionId, value) => emit('comment', criterionId, value)"
      />
    </section>

    <EaEmpty
      v-else
      title="Waiting for review criteria"
      description="The eligibility review will appear here as chart evidence is prepared for clinician review."
      class="rounded-[1.75rem] border border-dashed border-border bg-card py-14"
    />

    <div class="sticky bottom-3 z-10 mt-2">
      <div class="grid gap-3 rounded-[1.5rem] border border-border bg-background/95 p-4 shadow-[0_16px_30px_rgba(26,26,26,0.08)] backdrop-blur">
        <div
          v-if="showActionLoading"
          class="flex items-start gap-3 rounded-[1.25rem] border border-border bg-card px-4 py-3"
          aria-live="polite"
        >
          <span class="loading-spinner" aria-hidden="true" />
          <div class="grid gap-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Preparing next step</span>
            <p class="text-sm text-muted-foreground">
              {{ submitting
                ? 'Building the final submission review from the approved answers.'
                : 'The eligibility review is still being prepared before you can continue.' }}
            </p>
          </div>
        </div>
        <EaButton
          variant="accent"
          size="lg"
          class="w-full justify-center sm:w-auto"
          :disabled="!isSubmitReady"
          @click="emit('submit')"
        >
          {{ actionButtonLabel }}
        </EaButton>
      </div>
    </div>
  </section>
</template>
