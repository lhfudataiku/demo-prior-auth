<script setup lang="ts">
defineProps<{
  policyId: string | null
  policyLabel: string | null
  reviewScope: {
    route_label: string
    phase_label: string
    cluster_label: string
    route_id: string
    phase_id: string
    cluster_id: string
  } | null
}>()
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <p class="eyebrow">Selected scope</p>
      <h2>Policy Review</h2>
    </div>
    <dl class="summary-stack">
      <div>
        <dt>Policy</dt>
        <dd>{{ policyLabel ?? '—' }}</dd>
        <dd class="summary-meta">{{ policyId ?? '—' }}</dd>
      </div>
      <div>
        <dt>Route</dt>
        <dd>{{ reviewScope?.route_label ?? '—' }}</dd>
        <dd class="summary-meta">{{ reviewScope?.route_id ?? '—' }}</dd>
      </div>
      <div>
        <dt>Phase</dt>
        <dd>{{ reviewScope?.phase_label ?? '—' }}</dd>
        <dd class="summary-meta">{{ reviewScope?.phase_id ?? '—' }}</dd>
      </div>
      <div>
        <dt>Cluster</dt>
        <dd>{{ reviewScope?.cluster_label ?? '—' }}</dd>
        <dd class="summary-meta">{{ reviewScope?.cluster_id ?? '—' }}</dd>
      </div>
    </dl>
  </section>
</template>
