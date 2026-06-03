<script setup lang="ts">
interface Props {
  variant?: "default" | "strong" | "flat";
  padding?: string;
  rounded?: string;
  tag?: string;
}
const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  padding: "p-5",
  rounded: "rounded-lg",
  tag: "div",
});
</script>

<template>
  <component
    :is="props.tag"
    :class="[
      props.variant === 'default' ? 'glass' : '',
      props.variant === 'strong' ? 'glass-strong' : '',
      props.variant === 'flat' ? 'glass-flat' : '',
      props.padding,
      props.rounded,
    ]"
  >
    <slot />
  </component>
</template>
