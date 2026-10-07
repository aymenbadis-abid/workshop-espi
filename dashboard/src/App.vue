<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ChartCard from "./components/ChartCard.vue";

const MAX_POINTS = 60;
const BOARD_ID = "esp32-01";
const readings = ref([]);
const alerts = ref([]);
const status = ref(null);
const connected = ref(false);
const commandMessage = ref("");
const videoUrl = "/video/stream";
let socket;
let pingTimer;

const series = computed(() => {
  const take = (key) => readings.value.map((row) => ({ ts: row.ts, value: row[key] }));
  return {
    temp: take("temp"),
    hum: take("hum"),
    gas: take("gas"),
    light: take("light"),
  };
});

const simulated = computed(() => new Set(readings.value.at(-1)?.simulated ?? []));

const statusLabel = computed(() => {
  if (!status.value) return "En attente de la carte";
  return status.value.online ? "En ligne" : "Hors ligne";
});

function pushReading(row) {
  if (row.device !== BOARD_ID) return;
  readings.value = readings.value.concat(row).slice(-MAX_POINTS);
}

async function loadInitial() {
  const [telemetryRes, alertsRes, statusRes] = await Promise.all([
    fetch("/api/v1/telemetry?limit=60"),
    fetch("/api/v1/alerts?limit=20"),
    fetch("/api/v1/status"),
  ]);
  if (telemetryRes.ok) {
    const rows = await telemetryRes.json();
    readings.value = rows.filter((row) => row.device === BOARD_ID).slice(-MAX_POINTS);
  }
  if (alertsRes.ok) alerts.value = await alertsRes.json();
  if (statusRes.ok) {
    const rows = await statusRes.json();
    status.value = rows.find((row) => row.device === BOARD_ID) ?? null;
  }
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/api/v1/ws`);
  socket.onopen = () => {
    connected.value = true;
  };
  socket.onclose = () => {
    connected.value = false;
    window.setTimeout(connect, 2000);
  };
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.kind === "telemetry") pushReading(message.data);
    if (message.kind === "alert") {
      alerts.value = [message.data, ...alerts.value].slice(0, 20);
      if (message.data.type === "ack") commandMessage.value = message.data.message;
    }
    if (message.kind === "status" && message.data?.device === BOARD_ID) status.value = message.data;
  };
}

async function sendCommand(body) {
  commandMessage.value = "Envoi…";
  const response = await fetch("/api/v1/commands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  commandMessage.value = response.ok ? "Commande envoyée" : "Échec de la commande";
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("fr-FR");
}

onMounted(async () => {
  await loadInitial();
  connect();
  pingTimer = window.setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, 25000);
});

onBeforeUnmount(() => {
  window.clearInterval(pingTimer);
  if (socket) socket.onclose = null;
  socket?.close();
});
</script>

<template>
  <header>
    <h1>Sentinel-X</h1>
    <p class="live" :class="{ ok: connected }">
      {{ connected ? "Temps réel connecté" : "Temps réel coupé" }}
    </p>
  </header>
  <main>
    <div class="charts">
      <ChartCard label="Température (°C)" color="#3ddc97" :simulated="simulated.has('temp')" :points="series.temp" />
      <ChartCard label="Humidité (%)" color="#59b6f0" :simulated="simulated.has('hum')" :points="series.hum" />
      <ChartCard label="Gaz" color="#e6b35a" :simulated="simulated.has('gas')" :points="series.gas" />
      <ChartCard label="Lumière" color="#d0d7e2" :simulated="false" :points="series.light" />
    </div>
    <div class="stack">
      <section class="panel">
        <h2>État du boîtier</h2>
        <p>{{ statusLabel }}</p>
        <p class="muted" v-if="status">{{ status.device }} · IP {{ status.ip || "inconnue" }} · uptime {{ status.uptime ?? "—" }} s</p>
        <p class="muted" v-else>En attente de la carte ESP32.</p>
      </section>
      <section class="panel">
        <h2>Alertes</h2>
        <p v-if="alerts.length === 0" class="muted">Aucune alerte</p>
        <ul v-else>
          <li v-for="alert in alerts" :key="alert.id" :class="alert.severity">
            <strong>{{ alert.type }}</strong> — {{ alert.message }}
            <div class="muted">{{ formatTime(alert.created_at) }} · {{ alert.source }}</div>
          </li>
        </ul>
      </section>
      <section class="panel">
        <h2>Vidéo</h2>
        <img class="video" :src="videoUrl" alt="Flux caméra du serveur" />
      </section>
      <section class="panel">
        <h2>Commandes</h2>
        <p class="muted">Scénarios</p>
        <div class="buttons">
          <button type="button" @click="sendCommand({ scenario: 'normal' })">Normal</button>
          <button type="button" @click="sendCommand({ scenario: 'drift' })">Dérive</button>
          <button type="button" @click="sendCommand({ scenario: 'gas_leak' })">Fuite de gaz</button>
          <button type="button" @click="sendCommand({ scenario: 'reset' })">Reset</button>
        </div>
        <p class="muted">LED rouge</p>
        <div class="buttons">
          <button type="button" @click="sendCommand({ target: 'led_red', state: 'on' })">Allumer</button>
          <button type="button" @click="sendCommand({ target: 'led_red', state: 'off' })">Éteindre</button>
        </div>
        <p class="muted">LED verte</p>
        <div class="buttons">
          <button type="button" @click="sendCommand({ target: 'led_green', state: 'on' })">Allumer</button>
          <button type="button" @click="sendCommand({ target: 'led_green', state: 'off' })">Éteindre</button>
        </div>
        <p class="muted">Buzzer</p>
        <div class="buttons">
          <button type="button" @click="sendCommand({ target: 'buzzer', state: 'on' })">Allumer</button>
          <button type="button" @click="sendCommand({ target: 'buzzer', state: 'off' })">Éteindre</button>
          <button type="button" @click="sendCommand({ auto: true })">Auto</button>
        </div>
        <p class="muted">{{ commandMessage }}</p>
      </section>
    </div>
  </main>
</template>
