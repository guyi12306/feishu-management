<script setup lang="ts">
import { RouterView } from "vue-router";
import SideBar from "./SideBar.vue";
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden">
    <SideBar />
    <main class="flex-1 h-full overflow-hidden flex">
      <RouterView />
    </main>
  </div>
</template>
