<script setup lang="ts">
import { computed } from 'vue'
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { Check, ChevronDown } from 'lucide-vue-next'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  modelValue: string | undefined
  options: (string | { value: string; label: string })[]
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const EMPTY_VALUE_SENTINEL = '__ea_empty__'

const normalizedOptions = computed(() =>
  props.options.map((option) => {
    const normalized = typeof option === 'string' ? { value: option, label: option } : option
    return {
      ...normalized,
      value: normalized.value === '' ? EMPTY_VALUE_SENTINEL : normalized.value,
    }
  }),
)

const internalValue = computed(() => {
  if (props.modelValue === '') return undefined
  return props.modelValue
})

function emitModelValue(value: string) {
  emit('update:modelValue', value === EMPTY_VALUE_SENTINEL ? '' : value)
}
</script>

<template>
  <SelectRoot
    :model-value="internalValue"
    :disabled="disabled"
    @update:model-value="emitModelValue($event as string)"
  >
    <SelectTrigger
      v-bind="$attrs"
      class="flex h-11 items-center justify-between gap-2 rounded-2xl border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors hover:bg-accent/40 focus:outline-none focus:ring-2 focus:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-60 data-[placeholder]:text-muted-foreground"
    >
      <SelectValue :placeholder="placeholder || 'Select an option'" class="truncate" />
      <SelectIcon as-child>
        <ChevronDown class="h-4 w-4 shrink-0 opacity-60" />
      </SelectIcon>
    </SelectTrigger>

    <SelectPortal>
      <SelectContent
        position="popper"
        :side-offset="6"
        class="z-50 max-h-[18rem] min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-2xl border border-border bg-popover text-popover-foreground shadow-lg"
      >
        <SelectViewport class="p-1">
          <SelectItem
            v-for="option in normalizedOptions"
            :key="option.value"
            :value="option.value"
            class="relative flex cursor-pointer select-none items-center rounded-xl py-2 pl-8 pr-3 text-sm text-foreground outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[state=checked]:font-medium data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
          >
            <SelectItemIndicator class="absolute left-2 inline-flex items-center">
              <Check class="h-4 w-4" />
            </SelectItemIndicator>
            <SelectItemText>{{ option.label }}</SelectItemText>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>
