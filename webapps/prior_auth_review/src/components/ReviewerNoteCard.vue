<script setup lang="ts">
import type { ReviewMetadata } from '../Api'
import { EaInput, EaTextarea } from './ui'

defineProps<{
  reviewMetadata: ReviewMetadata
}>()

const emit = defineEmits<{
  'update-reviewer': [value: string]
  'update-comment': [value: string]
}>()
</script>

<template>
  <section class="rounded-[1.5rem] border border-sidebar-border bg-[rgba(248,244,228,0.96)] p-5 text-[#1a1a1a] shadow-sm">
    <div class="mb-4 space-y-1">
      <p class="font-mono text-xs uppercase tracking-[0.08em] text-[#1a1a1a]/56">Submission metadata</p>
      <h2 class="font-serif text-2xl font-semibold">Reviewer note</h2>
    </div>
    <div class="grid gap-4">
      <label class="grid gap-2">
        <span class="font-mono text-xs uppercase tracking-[0.08em] text-[#1a1a1a]/56">Reviewer</span>
        <EaInput
          :model-value="reviewMetadata.reviewer ?? ''"
          placeholder="POC reviewer"
          @update:model-value="emit('update-reviewer', $event)"
        />
      </label>
      <label class="grid gap-2">
        <span class="font-mono text-xs uppercase tracking-[0.08em] text-[#1a1a1a]/56">Comment</span>
        <EaTextarea
          :model-value="reviewMetadata.comment ?? ''"
          :rows="4"
          placeholder="Optional reviewer note"
          @update:model-value="emit('update-comment', $event)"
        />
      </label>
      <p class="text-xs text-[#1a1a1a]/56">
        Notes entered here stay part of the deterministic review handoff.
      </p>
    </div>
  </section>
</template>
