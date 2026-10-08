<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

import { storeToken } from "../session.js";

const router = useRouter();
const email = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.value.trim(), password: password.value }),
    });
    if (!response.ok) {
      error.value = "Identifiants refusés";
      return;
    }
    const body = await response.json();
    if (!body.access_token) {
      error.value = "Identifiants refusés";
      return;
    }
    storeToken(body.access_token);
    await router.replace("/");
  } catch {
    error.value = "Identifiants refusés";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login-shell">
    <form class="login-card" @submit.prevent="submit">
      <p class="eyebrow">Salle serveurs</p>
      <h1>Sentinel-X</h1>
      <p class="note">Un compte admin est exigé pour lire la salle.</p>
      <label>
        Email
        <input v-model="email" type="email" autocomplete="username" required />
      </label>
      <label>
        Mot de passe
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="busy">{{ busy ? "Connexion…" : "Entrer" }}</button>
    </form>
  </div>
</template>
