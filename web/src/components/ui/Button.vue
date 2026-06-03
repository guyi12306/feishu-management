<script setup lang="ts">
interface Props {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}
const props = withDefaults(defineProps<Props>(), {
  variant: "primary",
  loading: false,
  disabled: false,
  type: "button",
});
</script>

<template>
  <button
    :type="props.type"
    :disabled="props.disabled || props.loading"
    :class="[
      'btn',
      props.variant === 'primary' && 'btn-primary',
      props.variant === 'secondary' && 'btn-secondary',
      props.variant === 'ghost' && 'btn-ghost',
      props.variant === 'danger' && 'bg-danger text-white hover:bg-red-600',
      (props.disabled || props.loading) && 'opacity-60 cursor-not-allowed',
    ]"
  >
    <span
      v-if="props.loading"
      class="w-3.5 h-3.5 rounded-full border-2 border-current border-r-transparent animate-spin"
    />
    <slot />
  </button>
</template>
