<script setup lang="ts">
import type { Screen2ReviewResult, Screen3Payload } from '../Api'

defineProps<{
  reviewResult: Screen2ReviewResult | null
  screen3: Screen3Payload | null
}>()
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <p class="eyebrow">Screen 3</p>
      <h2>Review summary</h2>
    </div>

    <div v-if="reviewResult" class="meta-row">
      <span class="status-badge">{{ reviewResult.approval_status }}</span>
      <span class="body-copy">human validated: {{ reviewResult.human_validated ? 'yes' : 'no' }}</span>
    </div>

    <div v-if="screen3" class="summary-stack">
      <dl class="summary-grid">
        <div>
          <dt>Total criteria</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.total }}</dd>
        </div>
        <div>
          <dt>Satisfied</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.satisfied }}</dd>
        </div>
        <div>
          <dt>Rejected</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.rejected }}</dd>
        </div>
        <div>
          <dt>Unresolved</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.unresolved }}</dd>
        </div>
      </dl>

      <div class="warning-list" v-if="screen3.payload.review_alerts.length">
        <p class="label">Review alerts</p>
        <ul>
          <li
            v-for="warning in screen3.payload.review_alerts"
            :key="`${warning.criterion_id ?? 'warning'}:${warning.type ?? 'warning'}:${warning.message}`"
          >
            {{ warning.message }}
          </li>
        </ul>
      </div>

      <div class="warning-list" v-if="screen3.payload.unresolved_criteria.length">
        <p class="label">Unresolved criteria</p>
        <ul>
          <li
            v-for="item in screen3.payload.unresolved_criteria"
            :key="String(item.criterion_id)"
          >
            {{ item.prompt }}
          </li>
        </ul>
      </div>

      <div class="answers-list">
        <p class="label">Rejected criteria</p>
        <ul>
          <li v-for="criterion in screen3.payload.rejected_criteria" :key="criterion.criterion_id">
            <strong>{{ criterion.criterion_id }}</strong> — {{ criterion.final_answer }} ({{ criterion.final_source }})
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
