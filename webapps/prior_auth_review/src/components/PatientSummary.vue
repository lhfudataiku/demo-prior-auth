<script setup lang="ts">
import type { PatientSummary } from '../Api'

defineProps<{
  patient: PatientSummary | null
  subjectId?: string
}>()
</script>

<template>
  <section class="rounded-[1.5rem] border border-sidebar-border bg-card p-5 text-card-foreground shadow-sm">
    <div class="mb-4 space-y-1">
      <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Patient</p>
      <h2 class="font-serif text-2xl font-semibold">Patient summary</h2>
    </div>
    <dl class="grid gap-4">
      <div class="grid gap-1">
        <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Subject ID</dt>
        <dd class="text-sm font-medium break-all">{{ patient?.subject_id ?? subjectId ?? '—' }}</dd>
      </div>
      <div class="grid gap-1 sm:grid-cols-2 sm:gap-4">
        <div class="grid gap-1">
          <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Gender</dt>
          <dd class="text-sm font-medium">{{ patient?.gender ?? '—' }}</dd>
        </div>
        <div class="grid gap-1">
          <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Age</dt>
          <dd class="text-sm font-medium">{{ patient?.age ?? '—' }}</dd>
        </div>
      </div>
      <div class="grid gap-1">
        <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Birth date</dt>
        <dd class="text-sm font-medium">{{ patient?.birth_date ?? '—' }}</dd>
      </div>
    </dl>
  </section>
</template>
