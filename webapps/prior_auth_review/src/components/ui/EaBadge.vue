<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../utils/css'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.04em]',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-background text-muted-foreground',
        route: 'border-dk-blue-grey/20 bg-dk-blue-soft text-dk-blue-grey',
        entry: 'border-dk-brown/20 bg-dk-orange-soft text-dk-brown',
        cluster: 'border-dk-dark-green/15 bg-dk-green/18 text-dk-dark-green',
        inherited: 'border-dk-blue/18 bg-dk-light-green/75 text-dk-blue-grey',
        positive: 'border-dk-dark-green/12 bg-dk-light-green text-dk-dark-green',
        warning: 'border-dk-brown/18 bg-dk-orange-soft text-dk-brown',
        critical: 'border-dk-brown/22 bg-dk-brown/15 text-dk-brown',
      },
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)

type BadgeVariants = VariantProps<typeof badgeVariants>

const props = defineProps<{
  tone?: BadgeVariants['tone'] | string
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <span :class="cn(badgeVariants({ tone: props.tone as BadgeVariants['tone'] }), props.class)">
    <slot />
  </span>
</template>
