<script setup lang="ts">
interface Props {
  hoverable?: boolean;
}
const props = withDefaults(defineProps<Props>(), { hoverable: false });
</script>

<template>
  <div
    class="card transition duration-200 ease-out-quart"
    :class="props.hoverable && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-glass-strong'"
  >
    <slot />
  </div>
</template>
