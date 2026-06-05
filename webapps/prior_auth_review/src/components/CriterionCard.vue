<script setup lang="ts">
import { computed } from 'vue'
import type { CriterionAnswer, CriterionRow } from '../Api'
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

const evidenceStateLabel = computed(() =>
  props.loading ? 'Loading' : labelForChartStatus(props.criterion.chart_result.status),
)
const criteriaStateLabel = computed(() => labelForCriterionState(props.criterion.ui_resolution.display_state))

const evidenceTone = computed(() => (props.loading ? 'neutral' : toneForStatus(props.criterion.chart_result.status)))

const criteriaTone = computed(() => toneForStatus(props.criterion.ui_resolution.display_state))

const criterionKindTone = computed(() => {
  const kind = props.criterion.criterion_kind
  if (kind === 'route_guard') return 'kind-route'
  if (kind === 'cluster_entry_guard') return 'kind-entry'
  if (kind === 'inherited_diagnosis') return 'kind-inherited'
  return 'kind-cluster'
})

const originLabel = computed(() => {
  if (props.origin === 'screen1') return 'Entered on Screen 1'
  if (props.origin === 'screen2') return 'Updated on Screen 2'
  return null
})

const evidenceCount = computed(() =>
  props.criterion.chart_result.sources.structured.length + props.criterion.chart_result.sources.notes.length,
)
</script>

<template>
  <article class="criterion-card" :data-state="criterion.ui_resolution.display_state">
    <div class="criterion-topline">
      <div class="chip-row">
        <div class="status-kv">
          <span class="label">Criterion type</span>
          <span class="kind-badge" :data-tone="criterionKindTone">{{ labelForCriterionKind(criterion.criterion_kind) }}</span>
        </div>
        <span v-if="criterion.required" class="detail-chip">Required</span>
        <span v-if="originLabel" class="detail-chip">{{ originLabel }}</span>
      </div>
      <div class="chip-row">
        <div class="status-kv">
          <span class="label">Criteria</span>
          <span class="status-chip" :data-tone="criteriaTone">{{ criteriaStateLabel }}</span>
        </div>
      </div>
    </div>

    <h3>{{ criterion.prompt }}</h3>

    <section class="criterion-section">
      <h4 class="section-title">Chart result</h4>
      <div class="status-kv">
        <span class="label">Evidence</span>
        <span class="status-chip status-chip--loading" :data-tone="evidenceTone">
          <span v-if="loading" class="loading-dot" aria-hidden="true" />
          {{ evidenceStateLabel }}
        </span>
      </div>
      <div class="chart-result-copy" :class="{ 'chart-result-copy--loading': loading }">
        <template v-if="loading">
          <span class="loading-row">
            <span class="loading-dot" aria-hidden="true" />
            The Structured Agent is gathering chart evidence for this criterion.
          </span>
        </template>
        <template v-else>
          {{ criterion.chart_result.justification || 'No chart explanation returned.' }}
        </template>
      </div>
    </section>

    <details class="evidence-panel" v-if="!loading && evidenceCount > 0">
      <summary>Clinical evidence ({{ evidenceCount }})</summary>
      <div class="evidence-stack">
        <div v-if="criterion.chart_result.sources.structured.length">
          <p class="label">Structured evidence</p>
          <pre class="evidence-pre">{{ JSON.stringify(criterion.chart_result.sources.structured, null, 2) }}</pre>
        </div>
        <div v-if="criterion.chart_result.sources.notes.length">
          <p class="label">Note evidence</p>
          <pre class="evidence-pre">{{ JSON.stringify(criterion.chart_result.sources.notes, null, 2) }}</pre>
        </div>
      </div>
    </details>

    <section class="criterion-section">
      <h4 class="section-title">Clinician review</h4>
      <div class="field-group vertical">
        <label class="field">
          <span>Answer</span>
          <select
            :value="answer?.answer === null || answer?.answer === undefined ? '' : String(answer.answer)"
            :disabled="readonly"
            @change="emit('answer', criterion.criterion_id, normalizeBoolean(($event.target as HTMLSelectElement).value))"
          >
            <option value="">Leave unanswered</option>
            <option value="true">Meets criterion</option>
            <option value="false">Does not meet criterion</option>
          </select>
        </label>
        <label class="field">
          <span>Comment</span>
          <textarea
            rows="3"
            :value="answer?.comment ?? ''"
            :disabled="readonly"
            @input="emit('comment', criterion.criterion_id, ($event.target as HTMLTextAreaElement).value)"
            placeholder="Optional reviewer note"
          />
        </label>
      </div>
    </section>

    <div v-if="criterion.ui_resolution.conflict_flag" class="conflict-box">
      {{
        criterion.ui_resolution.comment_guidance
          || criterion.ui_resolution.conflict_reason
          || 'Clinician answer differs from chart-backed evidence.'
      }}
    </div>
  </article>
</template>
