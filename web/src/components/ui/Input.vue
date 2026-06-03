<script setup lang="ts">
interface Props {
  modelValue: string;
  type?: string;
  placeholder?: string;
  label?: string;
  hint?: string;
  error?: string;
  autocomplete?: string;
  disabled?: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  type: "text",
  placeholder: "",
});

defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <label class="block">
    <span v-if="props.label" class="text-caption text-ink-700 mb-1.5 block">
      {{ props.label }}
    </span>
    <input
      class="input"
      :type="props.type"
      :placeholder="props.placeholder"
      :autocomplete="props.autocomplete"
      :disabled="props.disabled"
      :value="props.modelValue"
      @input="(e) => $emit('update:modelValue', (e.target as HTMLInputElement).value)"
    />
    <span v-if="props.hint && !props.error" class="text-caption mt-1.5 block">
      {{ props.hint }}
    </span>
    <span v-if="props.error" class="text-caption text-danger mt-1.5 block">
      {{ props.error }}
    </span>
  </label>
</template>
