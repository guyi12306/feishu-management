import { defineStore } from "pinia";
import { ref } from "vue";

import { authApi, type User } from "@/api/auth";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const checked = ref(false);

  async function fetchMe() {
    user.value = await authApi.me();
    checked.value = true;
  }

  async function login(username: string, password: string) {
    user.value = await authApi.login(username, password);
    checked.value = true;
  }

  async function logout() {
    try {
      await authApi.logout();
    } finally {
      user.value = null;
    }
  }

  return { user, checked, fetchMe, login, logout };
});
