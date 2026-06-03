import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";

import { useAuthStore } from "@/stores/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/Login.vue"),
    meta: { public: true },
  },
  {
    path: "/",
    component: () => import("@/components/layout/AppShell.vue"),
    children: [
      { path: "", redirect: "/chat" },
      {
        path: "chat/:conversationId(\\d+)?",
        name: "chat",
        component: () => import("@/views/Chat.vue"),
      },
      {
        path: "workflows",
        name: "workflows",
        component: () => import("@/views/Workflows/Index.vue"),
      },
      {
        path: "workflows/:id(\\d+)",
        name: "workflow-editor",
        component: () => import("@/views/Workflows/Editor.vue"),
      },
      {
        path: "settings",
        name: "settings",
        component: () => import("@/views/Settings.vue"),
      },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.checked) {
    await auth.fetchMe();
  }
  if (!to.meta.public && !auth.user) {
    return { name: "login", query: { from: to.fullPath } };
  }
  if (to.name === "login" && auth.user) {
    return { name: "chat" };
  }
});

export default router;
