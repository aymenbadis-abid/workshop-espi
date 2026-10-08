import { createRouter, createWebHistory } from "vue-router";

import { readToken } from "./session.js";
import LoginView from "./views/LoginView.vue";
import RoomView from "./views/RoomView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: RoomView },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  if (to.meta.public) return true;
  if (!readToken()) return "/login";
  return true;
});

export default router;
