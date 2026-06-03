<script setup lang="ts">
import type { Screen2ReviewResult, Screen3Payload } from '../Api'
import { humanizeToken, labelForCriterionKind, labelForCriterionState, toneForStatus } from '../uiLabels'

defineProps<{
  reviewResult: Screen2ReviewResult | null
  screen3: Screen3Payload | null
}>()
</script>

<template>
  <section class="page-stack" v-if="screen3">
    <header class="page-header">
      <div>
        <h1>Audited summary</h1>
        <p class="hero-copy">
          Final deterministic summary after clinician review.
        </p>
      </div>
      <div class="status-kv">
        <span class="label">Status</span>
        <span class="status-chip" :data-tone="toneForStatus(screen3.status)">{{ humanizeToken(screen3.status) }}</span>
      </div>
    </header>

    <section class="panel">
      <div class="section-header">
        <p class="eyebrow">Outcome</p>
        <h2>Submission readiness</h2>
      </div>
      <div class="review-outcome-grid">
        <div class="outcome-tile">
          <span class="label">Human validated</span>
          <span class="status-chip" :data-tone="reviewResult?.human_validated ? 'positive' : 'neutral'">
            {{ reviewResult?.human_validated ? 'Yes' : 'No' }}
          </span>
        </div>
        <div class="outcome-tile">
          <span class="label">Submission ready</span>
          <span class="status-chip" :data-tone="screen3.payload.submission_ready ? 'positive' : 'warning'">
            {{ screen3.payload.submission_ready ? 'Yes' : 'No' }}
          </span>
        </div>
        <div class="outcome-tile">
          <span class="label">Conflicts</span>
          <span class="status-chip" :data-tone="screen3.payload.review_summary.criterion_totals.conflicts ? 'warning' : 'positive'">
            {{ screen3.payload.review_summary.criterion_totals.conflicts }}
          </span>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <p class="eyebrow">Counts</p>
        <h2>Review totals</h2>
      </div>
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
          <dt>Cluster status</dt>
          <dd>
            <span class="status-chip" :data-tone="toneForStatus(screen3.payload.review_summary.logic_evaluation.selected_cluster_status)">
              {{ labelForCriterionState(screen3.payload.review_summary.logic_evaluation.selected_cluster_status) }}
            </span>
          </dd>
        </div>
      </dl>
    </section>

    <section class="panel" v-if="screen3.payload.warnings.length">
      <div class="section-header">
        <p class="eyebrow">Warnings</p>
        <h2>Items needing attention</h2>
      </div>
      <ul class="evidence-list">
        <li v-for="warning in screen3.payload.warnings" :key="warning">{{ warning }}</li>
      </ul>
    </section>

    <section class="panel" v-if="screen3.payload.unanswered_required_items.length">
      <div class="section-header">
        <p class="eyebrow">Unanswered required items</p>
        <h2>Resolve before submission</h2>
      </div>
      <ul class="answer-list">
        <li v-for="item in screen3.payload.unanswered_required_items" :key="String(item.criterion_id ?? item.prompt)">
          <strong>{{ item.prompt }}</strong>
          <span class="summary-meta">{{ item.criterion_id ?? 'Pending criterion' }}</span>
          <div class="chip-row">
            <span class="kind-badge" :data-tone="item.criterion_kind === 'route_guard' ? 'kind-route' : item.criterion_kind === 'cluster_entry_guard' ? 'kind-entry' : item.criterion_kind === 'inherited_diagnosis' ? 'kind-inherited' : 'kind-cluster'">
              {{ labelForCriterionKind(String(item.criterion_kind ?? 'cluster_criterion')) }}
            </span>
            <span class="status-chip" data-tone="neutral">Required</span>
          </div>
        </li>
      </ul>
    </section>

    <section class="panel">
      <div class="section-header">
        <p class="eyebrow">Answered criteria</p>
        <h2>Resolved items</h2>
      </div>
      <ul class="answer-list">
        <li v-for="criterion in screen3.payload.answered_criteria" :key="criterion.criterion_id">
          <strong>{{ criterion.prompt }}</strong>
          <span class="summary-meta">{{ criterion.criterion_id }}</span>
          <div class="chip-row">
            <span class="kind-badge" :data-tone="criterion.criterion_kind === 'route_guard' ? 'kind-route' : criterion.criterion_kind === 'cluster_entry_guard' ? 'kind-entry' : criterion.criterion_kind === 'inherited_diagnosis' ? 'kind-inherited' : 'kind-cluster'">
              {{ labelForCriterionKind(criterion.criterion_kind) }}
            </span>
            <span class="status-chip" :data-tone="toneForStatus(criterion.display_state)">
              {{ labelForCriterionState(criterion.display_state) }}
            </span>
          </div>
        </li>
      </ul>
    </section>
  </section>
</template>
