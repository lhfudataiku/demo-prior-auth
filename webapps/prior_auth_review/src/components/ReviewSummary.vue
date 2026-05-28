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
          <dt>Answered</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.answered }}</dd>
        </div>
        <div>
          <dt>Unanswered required</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.unanswered_required }}</dd>
        </div>
        <div>
          <dt>Conflicts</dt>
          <dd>{{ screen3.payload.review_summary.criterion_totals.conflicts }}</dd>
        </div>
      </dl>

      <div class="warning-list" v-if="screen3.payload.warnings.length">
        <p class="label">Warnings</p>
        <ul>
          <li v-for="warning in screen3.payload.warnings" :key="warning">{{ warning }}</li>
        </ul>
      </div>

      <div class="warning-list" v-if="screen3.payload.unanswered_required_items.length">
        <p class="label">Unanswered required items</p>
        <ul>
          <li
            v-for="item in screen3.payload.unanswered_required_items"
            :key="String(item.criterion_id)"
          >
            {{ item.prompt }}
          </li>
        </ul>
      </div>

      <div class="answers-list">
        <p class="label">Answered criteria</p>
        <ul>
          <li v-for="criterion in screen3.payload.answered_criteria" :key="criterion.criterion_id">
            <strong>{{ criterion.criterion_id }}</strong> — {{ criterion.final_answer }} ({{ criterion.final_source }})
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
