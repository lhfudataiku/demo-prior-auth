<script setup lang="ts">
import type { PatientSummary } from '../Api'

defineProps<{
  patient: PatientSummary | null
  subjectId?: string
}>()
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <p class="eyebrow">Patient</p>
      <h2>Patient summary</h2>
    </div>
    <dl class="summary-stack">
      <div>
        <dt>Subject ID</dt>
        <dd>{{ patient?.subject_id ?? subjectId ?? '—' }}</dd>
      </div>
      <div>
        <dt>Gender</dt>
        <dd>{{ patient?.gender ?? '—' }}</dd>
      </div>
      <div>
        <dt>Birth date</dt>
        <dd>{{ patient?.birth_date ?? '—' }}</dd>
      </div>
      <div>
        <dt>Age</dt>
        <dd>{{ patient?.age ?? '—' }}</dd>
      </div>
    </dl>
  </section>
</template>
