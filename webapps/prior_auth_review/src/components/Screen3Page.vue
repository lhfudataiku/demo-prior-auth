<script setup lang="ts">
import { computed } from 'vue'
import type { AttentionItem, Screen2ReviewResult, Screen3Payload } from '../Api'
import { EaBadge, EaButton, EaEmpty } from './ui'
import { humanizeToken, labelForCriterionKind, labelForCriterionState, toneForStatus } from '../uiLabels'

function kindTone(value: string | null | undefined): 'route' | 'entry' | 'inherited' | 'cluster' {
  if (value === 'route_guard') return 'route'
  if (value === 'cluster_entry_guard') return 'entry'
  if (value === 'inherited_diagnosis') return 'inherited'
  return 'cluster'
}

function alertKey(alert: AttentionItem): string {
  return `${alert.criterion_id ?? 'alert'}:${alert.type ?? 'alert'}:${alert.message}`
}

function finalSourceTone(value: string | null | undefined) {
  if (value === 'clinician') return 'cluster'
  if (value === 'chart') return 'positive'
  return 'neutral'
}

const props = defineProps<{
  reviewResult: Screen2ReviewResult | null
  screen3: Screen3Payload | null
}>()

const emit = defineEmits<{
  'jump-to-criterion': [criterionId: string]
}>()

const overallStatusLabel = computed(() =>
  labelForCriterionState(props.screen3?.payload.review_summary.logic_evaluation.selected_cluster_status ?? props.screen3?.status),
)
const submissionReadyLabel = computed(() => (props.screen3?.payload.submission_ready ? 'Ready' : 'Hold'))
</script>

<template>
  <section v-if="screen3" class="space-y-6">
    <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="space-y-2">
        <h1 class="font-serif text-3xl font-semibold text-foreground lg:text-4xl">Audited summary</h1>
        <p class="max-w-3xl text-sm text-muted-foreground lg:text-base">
          Final deterministic summary after clinician review.
        </p>
      </div>
      <div class="grid gap-2">
        <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Status</span>
        <p class="font-serif text-3xl font-semibold text-foreground">{{ overallStatusLabel }}</p>
      </div>
    </header>

    <section class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
      <div class="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-1">
          <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Outcome</p>
          <h2 class="font-serif text-2xl font-semibold text-foreground">Submission readiness</h2>
        </div>
        <div class="grid gap-2">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Submission ready</span>
          <p class="font-serif text-3xl font-semibold text-foreground">{{ submissionReadyLabel }}</p>
        </div>
      </div>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Total criteria</span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ screen3.payload.review_summary.criterion_totals.total }}
          </p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Satisfied</span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ screen3.payload.review_summary.criterion_totals.satisfied }}
          </p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Unresolved</span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ screen3.payload.review_summary.criterion_totals.unresolved }}
          </p>
        </div>
        <div class="rounded-[1.5rem] border border-border bg-card px-5 py-5 shadow-sm">
          <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Rejected</span>
          <p class="mt-3 font-serif text-3xl font-semibold text-foreground">
            {{ screen3.payload.review_summary.criterion_totals.rejected }}
          </p>
        </div>
      </div>
    </section>

    <section
      v-if="screen3.payload.review_alerts.length"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Review alerts</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Review-level issues</h2>
      </div>
      <div class="grid gap-3">
        <article
          v-for="alert in screen3.payload.review_alerts"
          :key="alertKey(alert)"
          class="rounded-[1.5rem] border border-dk-orange/30 bg-background px-5 py-5"
        >
          <div class="flex flex-wrap items-center gap-2">
            <EaBadge tone="warning">{{ humanizeToken(alert.type ?? 'alert') }}</EaBadge>
          </div>
          <h3 class="mt-4 font-serif text-xl font-semibold text-foreground">
            {{ humanizeToken(alert.type ?? 'review_alert') }}
          </h3>
          <div class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Justification</span>
            <p class="text-sm leading-6 text-muted-foreground">{{ alert.message }}</p>
          </div>
        </article>
      </div>
    </section>

    <section
      v-if="screen3.payload.unresolved_criteria.length"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Unresolved criteria</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Resolve before submission</h2>
      </div>
      <div class="grid gap-3">
        <article
          v-for="criterion in screen3.payload.unresolved_criteria"
          :key="criterion.criterion_id"
          class="rounded-[1.5rem] border border-border bg-background px-5 py-5"
        >
          <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="flex flex-wrap items-center gap-2">
              <EaBadge :tone="kindTone(criterion.criterion_kind)">
                {{ labelForCriterionKind(criterion.criterion_kind) }}
              </EaBadge>
              <EaBadge tone="neutral">{{ criterion.criterion_id }}</EaBadge>
            </div>
            <div class="space-y-1 lg:text-right">
              <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Eligibility</span>
              <div class="flex lg:justify-end">
                <EaBadge :tone="toneForStatus(criterion.display_state)">
                  {{ labelForCriterionState(criterion.display_state) }}
                </EaBadge>
              </div>
            </div>
          </div>
          <h3 class="mt-4 font-serif text-xl font-semibold text-foreground">{{ criterion.prompt }}</h3>
          <div class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Justification</span>
            <p class="text-sm leading-6 text-muted-foreground">
              {{ criterion.justification || 'This item still requires clinician input before the submission package can be finalized.' }}
            </p>
          </div>
          <EaButton
            variant="ghost"
            size="sm"
            class="mt-4 justify-start px-0"
            @click="emit('jump-to-criterion', criterion.criterion_id)"
          >
            Resolve in Screen 2
          </EaButton>
        </article>
      </div>
    </section>

    <section
      v-if="screen3.payload.rejected_criteria.length"
      class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm"
    >
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Rejected criteria</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Resolve before submission</h2>
      </div>
      <div
        class="grid gap-3"
      >
        <article
          v-for="criterion in screen3.payload.rejected_criteria"
          :key="criterion.criterion_id"
          class="rounded-[1.5rem] border border-border bg-background px-5 py-5"
        >
          <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="flex flex-wrap items-center gap-2">
              <EaBadge :tone="kindTone(criterion.criterion_kind)">
                {{ labelForCriterionKind(criterion.criterion_kind) }}
              </EaBadge>
              <EaBadge tone="neutral">{{ criterion.criterion_id }}</EaBadge>
              <EaBadge v-if="criterion.conflict_flag" tone="warning">Clinician override</EaBadge>
            </div>
            <div class="space-y-1 lg:text-right">
              <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Eligibility</span>
              <div class="flex lg:justify-end">
                <EaBadge :tone="toneForStatus(criterion.display_state)">
                  {{ labelForCriterionState(criterion.display_state) }}
                </EaBadge>
              </div>
            </div>
          </div>
          <h3 class="mt-4 font-serif text-xl font-semibold text-foreground">{{ criterion.prompt }}</h3>
          <div v-if="criterion.final_source !== 'unresolved'" class="mt-5 flex flex-wrap items-center gap-2">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Evidence:</span>
            <EaBadge :tone="finalSourceTone(criterion.final_source)">
              {{ humanizeToken(criterion.final_source) }}
            </EaBadge>
          </div>
          <div class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Justification</span>
            <p class="text-sm leading-6 text-muted-foreground">
              {{ criterion.justification || 'No chart justification returned.' }}
            </p>
          </div>
          <div v-if="criterion.comment" class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Clinician comment</span>
            <p class="text-sm leading-6 text-muted-foreground">{{ criterion.comment }}</p>
          </div>
          <div v-else-if="criterion.conflict_flag && criterion.conflict_reason" class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Override note</span>
            <p class="text-sm leading-6 text-muted-foreground">{{ criterion.conflict_reason }}</p>
          </div>
          <EaButton
            variant="ghost"
            size="sm"
            class="mt-4 justify-start px-0"
            @click="emit('jump-to-criterion', criterion.criterion_id)"
          >
            Resolve in Screen 2
          </EaButton>
        </article>
      </div>
    </section>

    <section class="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
      <div class="mb-6 space-y-1">
        <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Satisfied criteria</p>
        <h2 class="font-serif text-2xl font-semibold text-foreground">Ready to submit</h2>
      </div>
      <div
        v-if="screen3.payload.satisfied_criteria.length"
        class="grid gap-3"
      >
        <article
          v-for="criterion in screen3.payload.satisfied_criteria"
          :key="criterion.criterion_id"
          class="rounded-[1.5rem] border border-border bg-background px-5 py-5"
        >
          <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="flex flex-wrap items-center gap-2">
              <EaBadge :tone="kindTone(criterion.criterion_kind)">
                {{ labelForCriterionKind(criterion.criterion_kind) }}
              </EaBadge>
              <EaBadge tone="neutral">{{ criterion.criterion_id }}</EaBadge>
              <EaBadge v-if="criterion.conflict_flag" tone="warning">Clinician override</EaBadge>
            </div>
            <div class="space-y-1 lg:text-right">
              <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Eligibility</span>
              <div class="flex lg:justify-end">
                <EaBadge :tone="toneForStatus(criterion.display_state)">
                  {{ labelForCriterionState(criterion.display_state) }}
                </EaBadge>
              </div>
            </div>
          </div>
          <h3 class="mt-4 font-serif text-xl font-semibold text-foreground">{{ criterion.prompt }}</h3>
          <div v-if="criterion.final_source !== 'unresolved'" class="mt-5 flex flex-wrap items-center gap-2">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Evidence:</span>
            <EaBadge :tone="finalSourceTone(criterion.final_source)">
              {{ humanizeToken(criterion.final_source) }}
            </EaBadge>
          </div>
          <div class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Justification</span>
            <p class="text-sm leading-6 text-muted-foreground">
              {{ criterion.justification || 'No chart justification returned.' }}
            </p>
          </div>
          <div v-if="criterion.comment" class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Clinician comment</span>
            <p class="text-sm leading-6 text-muted-foreground">{{ criterion.comment }}</p>
          </div>
          <div v-else-if="criterion.conflict_flag && criterion.conflict_reason" class="mt-4 space-y-1">
            <span class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Override note</span>
            <p class="text-sm leading-6 text-muted-foreground">{{ criterion.conflict_reason }}</p>
          </div>
        </article>
      </div>
      <EaEmpty
        v-else
        title="No satisfied criteria"
        description="No criteria currently end in a meets-criterion disposition."
        class="rounded-[1.5rem] border border-dashed border-border bg-background py-12"
      />
    </section>
  </section>
</template>
