<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import {
  TooltipRoot,
  TooltipTrigger,
  TooltipPortal,
  TooltipContent,
  TooltipProvider,
} from 'reka-ui'

defineProps<{ label?: string }>()
</script>

<template>
  <TooltipProvider :delay-duration="120">
    <TooltipRoot>
      <TooltipTrigger as-child>
        <button
          type="button"
          class="inline-flex items-center justify-center rounded-full text-muted-foreground/60 transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-dk-green/40"
          :aria-label="label || 'More information'"
        >
          <Info class="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipPortal>
        <TooltipContent
          :side-offset="6"
          :collision-padding="12"
          class="z-50 max-w-[264px] rounded-[0.85rem] border border-border bg-card px-3.5 py-2.5 text-left text-xs normal-case leading-5 tracking-normal text-foreground shadow-[0_14px_32px_rgba(26,26,26,0.16)]"
        >
          <slot />
        </TooltipContent>
      </TooltipPortal>
    </TooltipRoot>
  </TooltipProvider>
</template>
