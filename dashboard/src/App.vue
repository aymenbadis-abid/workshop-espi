<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ChartCard from "./components/ChartCard.vue";
import {
  BOARD_ID,
  TEMP_LIMITS,
  TEMP_LIMIT_CAPTION,
  cameraModelName,
  capital,
  channelState,
  deviceWord,
  formatMeasure,
  frenchAck,
  gasAlertWord,
  gasPresentation,
  gasTone,
  heatTone,
  heatWord,
  lightDecision,
  lightTone,
  lightWord,
  mergeBoardReadings,
  modeWord,
  modelCaption,
  modelCards,
  modelMeta,
  originTitle,
  rssiText,
  severityWord,
  splitAlerts,
  transitionsText,
  uptimeText,
  visitorLine,
} from "./reading.js";

const MAX_POINTS = 60;
const readings = ref([]);
const alerts = ref([]);
const status = ref(null);
const scores = ref({});
const connected = ref(false);
const commandMessage = ref("");
const cameraLive = ref(false);
const videoUrl = "/video/stream";
let socket;
let pingTimer;
let cameraTimer;
let syncTimer;
let probeGeneration = 0;

const latest = computed(() => readings.value.at(-1) ?? null);

const series = computed(() => {
  const take = (key) => readings.value.map((row) => ({ ts: row.ts, value: row[key] }));
  return {
    temp: take("temp"),
    hum: take("hum"),
    gas: take("gas"),
    light: take("light"),
  };
});

const gasView = computed(() => gasPresentation(latest.value));

const driftAlert = computed(() => alerts.value.find((row) => row.type === "anomaly") ?? null);
const personAlert = computed(() => alerts.value.find((row) => row.type === "person") ?? null);
const driftModel = computed(() => modelCaption(driftAlert.value));

const scoreRows = computed(() => Object.values(scores.value));
const modelSource = computed(() => {
  const board = scores.value[BOARD_ID];
  if (board?.models) return board.models;
  return scoreRows.value.find((row) => row?.models)?.models ?? null;
});
const loadedModels = computed(() => modelCards(modelSource.value));
const driftLines = computed(() =>
  scoreRows.value.map((row) => visitorLine(capital(deviceWord(row.device)), row.joint_drift)).filter(Boolean),
);
const silenceLines = computed(() =>
  scoreRows.value.map((row) => visitorLine(capital(deviceWord(row.device)), row.silence)).filter(Boolean),
);

const boardLead = computed(() => {
  if (!status.value) return "En attente de la carte ESP32";
  return status.value.online ? "En ligne" : "Hors ligne";
});

function rememberScore(body) {
  if (!body?.device) return;
  scores.value = { ...scores.value, [body.device]: body };
}

function pushReading(row) {
  readings.value = mergeBoardReadings(readings.value, [row], BOARD_ID, MAX_POINTS);
}

async function reloadReadings() {
  const response = await fetch("/api/v1/telemetry?limit=60");
  if (!response.ok) return;
  readings.value = mergeBoardReadings(readings.value, await response.json(), BOARD_ID, MAX_POINTS);
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("fr-FR");
}

function captionOf(alert) {
  return modelCaption(alert);
}

async function loadInitial() {
  const [telemetryRes, alertsRes, statusRes, scoringRes] = await Promise.all([
    fetch("/api/v1/telemetry?limit=60"),
    fetch("/api/v1/alerts?limit=100"),
    fetch("/api/v1/status"),
    fetch("/api/v1/scoring"),
  ]);
  if (telemetryRes.ok) {
    readings.value = mergeBoardReadings([], await telemetryRes.json(), BOARD_ID, MAX_POINTS);
  }
  if (alertsRes.ok) {
    const { findings, ack } = splitAlerts(await alertsRes.json());
    alerts.value = findings;
    if (ack) commandMessage.value = frenchAck(ack);
  }
  if (statusRes.ok) {
    const rows = await statusRes.json();
    status.value = rows.find((row) => row.device === BOARD_ID) ?? null;
  }
  if (scoringRes.ok) {
    const body = await scoringRes.json();
    const next = {};
    for (const row of body.devices || []) next[row.device] = row;
    scores.value = next;
  }
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/api/v1/ws`);
  socket.onopen = () => {
    connected.value = true;
    reloadReadings().catch(() => {});
  };
  socket.onclose = () => {
    connected.value = false;
    window.setTimeout(connect, 2000);
  };
  socket.onmessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.kind === "telemetry") pushReading(message.data);
    if (message.kind === "alert") {
      if (message.data?.type === "ack") {
        commandMessage.value = frenchAck(message.data);
        return;
      }
      alerts.value = [message.data, ...alerts.value].slice(0, 20);
    }
    if (message.kind === "status" && message.data?.device === BOARD_ID) status.value = message.data;
    if (message.kind === "scoring") rememberScore(message.data);
  };
}

async function sendCommand(body) {
  commandMessage.value = "Envoi…";
  try {
    const response = await fetch("/api/v1/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    commandMessage.value = response.ok ? "Commande envoyée" : "Échec de la commande";
  } catch {
    commandMessage.value = "Échec de la commande";
  }
}

async function probeCamera() {
  const generation = ++probeGeneration;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 4000);
  try {
    const response = await fetch(videoUrl, { cache: "no-store", signal: controller.signal });
    controller.abort();
    if (generation === probeGeneration) cameraLive.value = response.ok;
  } catch {
    if (generation === probeGeneration) cameraLive.value = false;
  } finally {
    window.clearTimeout(timer);
  }
}

function onVideoError() {
  cameraLive.value = false;
}

onMounted(async () => {
  try {
    await loadInitial();
  } catch {
    /* The banner stays on « non reçu » when the API is down. */
  }
  connect();
  probeCamera();
  pingTimer = window.setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, 25000);
  syncTimer = window.setInterval(() => {
    reloadReadings().catch(() => {});
  }, 2000);
  cameraTimer = window.setInterval(probeCamera, 20000);
});

onBeforeUnmount(() => {
  window.clearInterval(pingTimer);
  window.clearInterval(cameraTimer);
  window.clearInterval(syncTimer);
  probeGeneration += 1;
  if (socket) socket.onclose = null;
  socket?.close();
});
</script>

<template>
  <header>
    <h1>Sentinel-X</h1>
    <p class="live" :class="{ ok: connected }">
      {{ connected ? "Liaison des mesures ouverte" : "Liaison des mesures coupée" }}
    </p>
  </header>

  <section class="banner" aria-label="Lecture immédiate">
    <article>
      <h2>Carte</h2>
      <p class="lead">{{ boardLead }}</p>
      <p v-if="status" class="muted">IP {{ status.ip || "inconnue" }}</p>
      <p v-if="status" class="muted">Depuis le démarrage {{ uptimeText(status.uptime) }}</p>
      <p v-if="status" class="muted">{{ status.updated_at ? `Vu à ${formatTime(status.updated_at)}` : "Vu à non reçu" }}</p>
      <p class="muted">Signal Wi-Fi {{ rssiText(latest?.rssi) }}</p>
      <p>Mode {{ modeWord(latest?.manual) }}</p>
    </article>

    <article>
      <h2>Décision de la carte</h2>
      <p>
        <span class="pill" :class="heatTone(latest?.alert_heat)">Chaleur : {{ heatWord(latest?.alert_heat) }}</span>
      </p>
      <p>
        <span class="pill" :class="gasTone(latest?.alert_gas)">Gaz : {{ gasAlertWord(latest?.alert_gas) }}</span>
      </p>
      <p>
        <span class="pill" :class="lightTone(latest?.light_dark)">Lumière : {{ lightDecision(latest?.light_dark) }}</span>
      </p>
    </article>

    <article>
      <h2>Décision de l'IA</h2>
      <p class="lead">{{ driftAlert ? driftAlert.message : "Aucune dérive signalée" }}</p>
      <p v-if="driftAlert" class="muted">{{ capital(deviceWord(driftAlert.device)) }}</p>
      <p v-if="driftModel?.name" class="model">Modèle : {{ driftModel.name }}</p>
      <p v-if="modelMeta(driftModel)" class="muted">{{ modelMeta(driftModel) }}</p>
      <p v-if="driftModel?.detail" class="muted">{{ driftModel.detail }}</p>
      <p v-for="line in driftLines" :key="line">{{ line }}</p>
      <p v-for="line in silenceLines" :key="line">{{ line }}</p>
      <p class="lead">{{ personAlert ? personAlert.message : "Aucune personne signalée" }}</p>
      <p v-if="personAlert" class="model">{{ cameraModelName(personAlert) }}</p>
      <p v-if="personAlert" class="muted">{{ capital(deviceWord(personAlert.device)) }}</p>
      <p v-if="scoreRows.length === 0" class="muted">Score des capteurs non reçu</p>
      <ul v-else class="plain">
        <li v-for="line in loadedModels" :key="line">{{ line }}</li>
      </ul>
    </article>

    <article>
      <h2>Caméra</h2>
      <p class="lead">{{ cameraLive ? "Flux en cours" : "Caméra arrêtée" }}</p>
    </article>
  </section>

  <main>
    <div class="charts">
      <ChartCard
        label="Température"
        color="#3ddc97"
        :state="latest ? channelState(latest.simulated, 'temp') : ''"
        :points="series.temp"
        :limits="TEMP_LIMITS"
        :limit-caption="TEMP_LIMIT_CAPTION"
      >
        <p class="figure">{{ formatMeasure(latest.temp, 1) }} <span class="unit">°C</span></p>
        <p>
          <span class="pill" :class="heatTone(latest.alert_heat)">Chaleur : {{ heatWord(latest.alert_heat) }}</span>
        </p>
      </ChartCard>
      <ChartCard
        label="Humidité"
        color="#59b6f0"
        :state="latest ? channelState(latest.simulated, 'hum') : ''"
        :points="series.hum"
      >
        <p class="figure">{{ formatMeasure(latest.hum, 1) }} <span class="unit">%</span></p>
      </ChartCard>
      <ChartCard label="Gaz" color="#e6b35a" :state="gasView.state" :points="series.gas">
        <p class="figure">{{ gasView.figure }}</p>
        <p v-if="gasView.kind === 'real'">
          <span class="pill" :class="gasTone(gasView.alert)">Gaz : {{ gasAlertWord(gasView.alert) }}</span>
        </p>
        <p v-for="line in gasView.lines" :key="line" class="muted">{{ line }}</p>
      </ChartCard>
      <ChartCard
        label="Lumière"
        color="#d0d7e2"
        :state="latest ? channelState(latest.simulated, 'light') : ''"
        :points="series.light"
      >
        <p class="figure">{{ lightWord(latest.light) || formatMeasure(latest.light, 0) }}</p>
        <p v-if="lightWord(latest.light)" class="muted">{{ formatMeasure(latest.light, 0) }}</p>
        <p class="muted">{{ transitionsText(latest.transitions_1min) }}</p>
      </ChartCard>
    </div>

    <div class="stack">
      <section class="panel">
        <h2>Constats</h2>
        <p v-if="alerts.length === 0" class="muted">Aucun constat</p>
        <ul v-else>
          <li v-for="alert in alerts" :key="alert.id" :class="alert.severity">
            <div class="origin">{{ originTitle(alert) }}</div>
            <p class="message">{{ alert.message }}</p>
            <p v-if="alert.type === 'anomaly' && captionOf(alert)?.name" class="model">
              Modèle : {{ captionOf(alert).name }}
            </p>
            <p v-if="alert.type === 'anomaly' && modelMeta(captionOf(alert))" class="muted">
              {{ modelMeta(captionOf(alert)) }}
            </p>
            <p v-if="alert.type === 'anomaly' && captionOf(alert)?.detail" class="muted">
              {{ captionOf(alert).detail }}
            </p>
            <p v-if="alert.type === 'person'" class="model">{{ cameraModelName(alert) }}</p>
            <div class="muted">
              {{ severityWord(alert.severity) }} · {{ deviceWord(alert.device) }} · {{ formatTime(alert.created_at) }}
            </div>
          </li>
        </ul>
      </section>

      <section class="panel">
        <h2>Vidéo</h2>
        <div v-if="cameraLive" class="video-frame">
          <img class="video" :src="videoUrl" alt="Flux annoté" @error="onVideoError" />
        </div>
        <div v-else class="video-frame stopped">Caméra arrêtée</div>
        <p v-if="cameraLive" class="video-caption">YOLOv8n, personne</p>
      </section>
    </div>
  </main>

  <section class="panel commands">
    <h2>Commandes de démonstration</h2>
    <p class="note">
      Les scénarios ne remplissent que les voies marquées simulées. Un gaz réel ne suit pas la fuite. Le bouton fuite
      publie tout de même le constat « Pic de gaz simulé ».
    </p>
    <div class="buttons">
      <button type="button" @click="sendCommand({ scenario: 'normal' })">Normal</button>
      <button type="button" @click="sendCommand({ scenario: 'drift' })">Dérive</button>
      <button type="button" @click="sendCommand({ scenario: 'gas_leak' })">Fuite de gaz</button>
      <button type="button" @click="sendCommand({ scenario: 'reset' })">Reset</button>
    </div>

    <p class="muted">Voyant rouge</p>
    <div class="buttons">
      <button type="button" @click="sendCommand({ target: 'led_red', state: 'on' })">Allumer</button>
      <button type="button" @click="sendCommand({ target: 'led_red', state: 'off' })">Éteindre</button>
    </div>
    <p class="muted">Voyant vert</p>
    <div class="buttons">
      <button type="button" @click="sendCommand({ target: 'led_green', state: 'on' })">Allumer</button>
      <button type="button" @click="sendCommand({ target: 'led_green', state: 'off' })">Éteindre</button>
    </div>
    <p class="muted">Mode</p>
    <div class="buttons">
      <button type="button" @click="sendCommand({ auto: true })">Auto</button>
    </div>
    <p class="note">Auto rend les voyants à la carte : obscurité, chaleur ou gaz.</p>

    <p class="muted">Buzzer</p>
    <p class="note">
      En auto, le danger fait un bip fort et l'avertissement un bip plus court, plus espacé. Allumer force le bip
      fort. Éteindre coupe.
    </p>
    <div class="buttons">
      <button type="button" @click="sendCommand({ target: 'buzzer', state: 'on' })">Allumer</button>
      <button type="button" @click="sendCommand({ target: 'buzzer', state: 'off' })">Éteindre</button>
    </div>
    <p v-if="commandMessage" class="ack-line">{{ commandMessage }}</p>
    <p class="note">Recaler la référence gaz se fait sur la carte. Cet écran ne l'envoie pas.</p>
  </section>
</template>
