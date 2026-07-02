<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '../../utils/css'

const props = defineProps<{
  modelValue?: string
  rows?: number
  placeholder?: string
  disabled?: boolean
  class?: HTMLAttributes['class']
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>

<template>
  <textarea
    :value="props.modelValue ?? ''"
    :rows="props.rows ?? 4"
    :placeholder="props.placeholder"
    :disabled="props.disabled"
    :class="cn(
      'w-full rounded-2xl border border-input bg-background px-3 py-2.5 text-sm text-foreground shadow-sm transition-colors outline-none focus:ring-2 focus:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-60',
      props.class,
    )"
    @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
  />
</template>
