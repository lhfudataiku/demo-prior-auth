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
  <section class="rounded-[1.5rem] border border-sidebar-border bg-card p-5 text-card-foreground shadow-sm">
    <div class="mb-4 space-y-1">
      <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Selected scope</p>
      <h2 class="font-serif text-2xl font-semibold">Policy review</h2>
    </div>
    <dl class="grid gap-4">
      <div class="grid gap-1">
        <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Policy</dt>
        <dd class="text-sm font-medium">{{ policyLabel ?? '—' }}</dd>
        <dd class="font-mono text-xs text-muted-foreground break-all">{{ policyId ?? '—' }}</dd>
      </div>
      <div class="grid gap-1">
        <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Route</dt>
        <dd class="text-sm font-medium">{{ reviewScope?.route_label ?? '—' }}</dd>
        <dd class="font-mono text-xs text-muted-foreground break-all">{{ reviewScope?.route_id ?? '—' }}</dd>
      </div>
      <div class="grid gap-1 sm:grid-cols-2 sm:gap-4">
        <div class="grid gap-1">
          <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Phase</dt>
          <dd class="text-sm font-medium">{{ reviewScope?.phase_label ?? '—' }}</dd>
          <dd class="font-mono text-xs text-muted-foreground break-all">{{ reviewScope?.phase_id ?? '—' }}</dd>
        </div>
        <div class="grid gap-1">
          <dt class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Cluster</dt>
          <dd class="text-sm font-medium">{{ reviewScope?.cluster_label ?? '—' }}</dd>
          <dd class="font-mono text-xs text-muted-foreground break-all">{{ reviewScope?.cluster_id ?? '—' }}</dd>
        </div>
      </div>
    </dl>
  </section>
</template>
