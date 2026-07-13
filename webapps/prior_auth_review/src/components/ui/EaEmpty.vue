<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon?: Component
  title: string
  description?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center rounded-[1.5rem] border border-border bg-card px-6 py-10 text-center">
    <div
      v-if="icon"
      class="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground"
    >
      <component :is="icon" class="h-6 w-6" />
    </div>
    <h3 class="font-serif text-xl font-semibold text-foreground">{{ title }}</h3>
    <p v-if="description" class="mt-2 max-w-md text-sm text-muted-foreground">
      {{ description }}
    </p>
    <div class="mt-4">
      <slot />
    </div>
  </div>
</template>
