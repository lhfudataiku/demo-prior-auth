<script setup lang="ts">
import type { ReviewMetadata } from '../Api'

defineProps<{
  reviewMetadata: ReviewMetadata
}>()

const emit = defineEmits<{
  'update-reviewer': [value: string]
  'update-comment': [value: string]
}>()
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <p class="eyebrow">Submission metadata</p>
      <h2>Reviewer note</h2>
    </div>
    <label class="field">
      <span>Reviewer</span>
      <input
        type="text"
        :value="reviewMetadata.reviewer ?? ''"
        @input="emit('update-reviewer', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label class="field">
      <span>Comment</span>
      <textarea
        rows="4"
        :value="reviewMetadata.comment ?? ''"
        @input="emit('update-comment', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
  </section>
</template>
