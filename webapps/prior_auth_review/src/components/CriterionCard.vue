<script setup lang="ts">
import { computed } from 'vue'
import type { CriterionAnswer, CriterionRow } from '../Api'
import { EaBadge, EaSelect, EaTextarea } from './ui'
import { labelForChartStatus, labelForCriterionKind, labelForCriterionState, toneForStatus } from '../uiLabels'

const props = defineProps<{
  criterion: CriterionRow
  answer?: CriterionAnswer
  origin?: 'screen1' | 'screen2'
  readonly?: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  answer: [criterionId: string, value: boolean | null]
  comment: [criterionId: string, value: string]
}>()

function normalizeBoolean(value: string) {
  if (value === 'true') return true
  if (value === 'false') return false
  return null
}

function toneForKind(value: CriterionRow['criterion_kind']) {
  if (value === 'route_guard') return 'route'
  if (value === 'cluster_entry_guard') return 'entry'
  if (value === 'inherited_diagnosis') return 'inherited'
  return 'cluster'
}

const answerOptions = [
  { value: '__unset__', label: 'Leave unanswered' },
  { value: 'true', label: 'Meets criterion' },
  { value: 'false', label: 'Does not meet criterion' },
]

const evidenceStateLabel = computed(() =>
  props.loading ? 'Loading' : labelForChartStatus(props.criterion.chart_result.status),
)
const criteriaStateLabel = computed(() => labelForCriterionState(props.criterion.ui_resolution.display_state))

const evidenceTone = computed(() => (props.loading ? 'neutral' : toneForStatus(props.criterion.chart_result.status)))
const criteriaTone = computed(() => toneForStatus(props.criterion.ui_resolution.display_state))

const originLabel = computed(() => {
  if (props.origin === 'screen1') return 'Entered on Screen 1'
  if (props.origin === 'screen2') return 'Updated on Screen 2'
  return null
})

const evidenceCount = computed(() =>
  props.criterion.chart_result.sources.structured.length + props.criterion.chart_result.sources.notes.length,
)

const criterionArchetype = computed(() => props.criterion.planner_context?.criterion_archetype ?? null)
const retrievalStrategy = computed(() => props.criterion.planner_context?.retrieval_strategy ?? null)
const hasIncompleteChartEvidence = computed(() =>
  props.criterion.chart_result.status === 'Missing' || props.criterion.chart_result.status === 'Ambiguous',
)
const reviewRequiresAttention = computed(() =>
  hasIncompleteChartEvidence.value || props.criterion.ui_resolution.display_state !== 'satisfied',
)
const reviewGuidance = computed(() => {
  if (props.criterion.ui_resolution.conflict_flag) {
    return props.criterion.ui_resolution.comment_guidance
      || props.criterion.ui_resolution.conflict_reason
      || 'Clinician answer differs from chart-backed evidence.'
  }
  if (hasIncompleteChartEvidence.value) {
    return 'Chart evidence is incomplete for this criterion. Please review the case and add a clinician comment.'
  }
  if (!reviewRequiresAttention.value) return null
  if (props.criterion.ui_resolution.display_state === 'needs_clinician') {
    return 'Chart evidence is incomplete for this criterion. Please review the case and add a clinician comment.'
  }
  if (props.criterion.ui_resolution.display_state === 'not_satisfied') {
    return 'This criterion is not satisfied from the current evidence. Please review the result and add a clinician comment if context is needed.'
  }
  return 'Please review this criterion carefully and add a clinician comment when clarification is needed.'
})
</script>

<template>
  <article
    :class="[
      'scroll-mt-24 rounded-[1.75rem] border bg-card p-6 shadow-sm transition-shadow',
      criterion.ui_resolution.display_state === 'conflict'
        ? 'border-dk-orange/60'
        : 'border-border',
    ]"
  >
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <EaBadge :tone="toneForKind(criterion.criterion_kind)">
            {{ labelForCriterionKind(criterion.criterion_kind) }}
          </EaBadge>
          <EaBadge v-if="criterion.required" tone="neutral">Required</EaBadge>
          <EaBadge v-if="originLabel" tone="neutral">{{ originLabel }}</EaBadge>
        </div>
        <div class="space-y-2">
          <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">{{ criterion.criterion_id }}</p>
          <h3 class="font-serif text-2xl font-semibold text-foreground">{{ criterion.prompt }}</h3>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 lg:justify-end">
        <EaBadge :tone="criteriaTone">{{ criteriaStateLabel }}</EaBadge>
      </div>
    </div>

    <div class="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.9fr)]">
      <section class="grid gap-4 rounded-[1.5rem] border border-border bg-background p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="space-y-1">
            <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Chart result</p>
            <h4 class="font-serif text-xl font-semibold text-foreground">Clinical evidence</h4>
          </div>
          <EaBadge :tone="evidenceTone">{{ evidenceStateLabel }}</EaBadge>
        </div>

        <div
          class="rounded-[1.25rem] border border-border bg-card px-4 py-4 text-base leading-7 text-foreground"
          :class="{ 'text-muted-foreground': loading }"
        >
          <template v-if="loading">
            <span class="inline-flex items-center gap-3">
              <span class="loading-spinner loading-spinner--inline" aria-hidden="true" />
              The Structured Agent is gathering chart evidence for this criterion.
            </span>
          </template>
          <template v-else>
            {{ criterion.chart_result.justification || 'No chart explanation returned.' }}
          </template>
        </div>

        <details
          v-if="!loading && (evidenceCount > 0 || criterionArchetype || retrievalStrategy)"
          class="rounded-[1.25rem] border border-border bg-card px-4 py-4"
        >
          <summary class="cursor-pointer font-mono text-xs uppercase tracking-[0.08em] text-foreground">
            Clinical evidence ({{ evidenceCount }})
          </summary>
          <div class="mt-4 grid gap-4">
            <div v-if="criterionArchetype || retrievalStrategy" class="flex flex-wrap gap-2">
              <EaBadge v-if="criterionArchetype" tone="neutral">Archetype: {{ criterionArchetype }}</EaBadge>
              <EaBadge v-if="retrievalStrategy" tone="neutral">Strategy: {{ retrievalStrategy }}</EaBadge>
            </div>

            <div v-if="criterion.chart_result.sources.structured.length" class="grid gap-2">
              <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Structured evidence</p>
              <pre class="overflow-x-auto rounded-[1rem] border border-border bg-background p-3 font-mono text-xs text-foreground whitespace-pre-wrap break-words">{{ JSON.stringify(criterion.chart_result.sources.structured, null, 2) }}</pre>
            </div>

            <div v-if="criterion.chart_result.sources.notes.length" class="grid gap-2">
              <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Note evidence</p>
              <pre class="overflow-x-auto rounded-[1rem] border border-border bg-background p-3 font-mono text-xs text-foreground whitespace-pre-wrap break-words">{{ JSON.stringify(criterion.chart_result.sources.notes, null, 2) }}</pre>
            </div>
          </div>
        </details>
      </section>

      <section class="grid gap-4 rounded-[1.5rem] border border-border bg-background p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="space-y-1">
            <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Clinician review</p>
            <h4 class="font-serif text-xl font-semibold text-foreground">Review and confirm</h4>
          </div>
          <EaBadge v-if="reviewRequiresAttention" tone="warning">Attention needed</EaBadge>
        </div>

        <label class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Answer</span>
          <EaSelect
            class="w-full"
            :model-value="answer?.answer === null || answer?.answer === undefined ? '' : String(answer.answer)"
            :options="answerOptions"
            :disabled="readonly"
            placeholder="Leave unanswered"
            @update:model-value="emit('answer', criterion.criterion_id, normalizeBoolean($event))"
          />
        </label>

        <label class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Comment</span>
          <EaTextarea
            :model-value="answer?.comment ?? ''"
            :disabled="readonly"
            :rows="4"
            placeholder="Optional reviewer note"
            @update:model-value="emit('comment', criterion.criterion_id, $event)"
          />
        </label>

        <div
          v-if="reviewGuidance"
          class="rounded-[1.25rem] border border-dk-orange/30 bg-dk-orange-soft px-4 py-3 text-sm text-dk-brown"
        >
          {{ reviewGuidance }}
        </div>
      </section>
    </div>
  </article>
</template>
