<script setup lang="ts">
import { computed } from 'vue'
import type { CriterionAnswer, CriterionRow } from '../Api'

const props = defineProps<{
  criterion: CriterionRow
  answer?: CriterionAnswer
  origin?: 'screen1' | 'screen2'
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

const evidenceStateLabel = computed(() => props.criterion.chart_result.status)
const criteriaStateLabel = computed(() => {
  const stateMap: Record<string, string> = {
    satisfied: 'Satisfied',
    not_satisfied: 'Not satisfied',
    needs_clinician: 'Needs clinician',
    conflict: 'Conflict',
    unanswered: 'Unanswered',
  }
  return stateMap[props.criterion.ui_resolution.display_state] ?? props.criterion.ui_resolution.display_state
})

const evidenceTone = computed(() => {
  const status = props.criterion.chart_result.status.toLowerCase()
  if (status === 'found') return 'positive'
  if (['ambiguous'].includes(status)) return 'warning'
  if (['missing', 'unreviewed'].includes(status)) return 'neutral'
  return status
})

const criteriaTone = computed(() => {
  const state = props.criterion.ui_resolution.display_state
  if (state === 'satisfied') return 'positive'
  if (['not_satisfied', 'conflict'].includes(state)) return 'warning'
  if (['needs_clinician', 'unanswered'].includes(state)) return 'neutral'
  return state
})

const criterionKindTone = computed(() => {
  const kind = props.criterion.criterion_kind
  if (kind === 'route_guard') return 'kind-route'
  if (kind === 'cluster_entry_guard') return 'kind-guard'
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
          <span class="kind-badge" :data-tone="criterionKindTone">{{ criterion.criterion_kind.replaceAll('_', ' ') }}</span>
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
        <span class="status-chip" :data-tone="evidenceTone">{{ evidenceStateLabel }}</span>
      </div>
      <div class="chart-result-copy">
        {{ criterion.chart_result.justification || 'No chart explanation returned.' }}
      </div>
    </section>

    <details class="evidence-panel" v-if="evidenceCount > 0">
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
            @input="emit('comment', criterion.criterion_id, ($event.target as HTMLTextAreaElement).value)"
            placeholder="Optional reviewer note"
          />
        </label>
      </div>
    </section>

    <div v-if="criterion.ui_resolution.conflict_flag" class="conflict-box">
      {{ criterion.ui_resolution.conflict_reason || 'Clinician answer differs from chart prefill.' }}
    </div>
  </article>
</template>
