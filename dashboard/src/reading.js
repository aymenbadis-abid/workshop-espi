/** French labels for the room screen. Stored fields only: nothing here invents a score. */

const BOARD_TYPES = new Set(["heat", "gas", "tamper"]);

const SEVERITY = {
  info: "information",
  warning: "avertissement",
  critical: "danger",
};

const CHANNEL = {
  temp: "température",
  hum: "humidité",
  gas: "gaz",
  light: "lumière",
};

const ACK = {
  "led_red:1": "Voyant rouge allumé",
  "led_red:0": "Voyant rouge éteint",
  "led_green:1": "Voyant vert allumé",
  "led_green:0": "Voyant vert éteint",
  "buzzer:1": "Buzzer allumé",
  "buzzer:0": "Buzzer éteint",
  auto: "Mode auto",
  "scenario:normal": "Scénario normal accepté",
  "scenario:drift": "Scénario dérive accepté",
  "scenario:gas_leak": "Scénario fuite de gaz accepté",
  "scenario:reset": "Scénario reset accepté",
};

const MODEL_ROLES = [
  ["couple", "Couple du simulateur"],
  ["room_temp", "Température de la salle"],
  ["room_hum", "Humidité de la salle"],
  ["room_couple", "Couple de la salle"],
];

export const TEMP_LIMITS = [
  { value: 27, label: "27 °C", color: "#e6b35a" },
  { value: 33, label: "33 °C", color: "#ef6f6c" },
];

export const TEMP_LIMIT_CAPTION =
  "Limites de la carte, pas une décision de l'IA. Avertissement dès 27 °C, effacement sous 25 °C. Danger dès 33 °C, effacement sous 31 °C.";

export const BOARD_ID = "esp32-01";

function isNumber(value) {
  return typeof value === "number" && !Number.isNaN(value);
}

export function formatMeasure(value, digits = 1) {
  if (!isNumber(value)) return "—";
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatLoose(value) {
  if (!isNumber(value)) return "—";
  const digits = Number.isInteger(value) ? 0 : 1;
  return formatMeasure(value, digits);
}

export function formatDelta(value) {
  if (!isNumber(value)) return "écart non reçu";
  const digits = Number.isInteger(value) ? 0 : 1;
  const body = formatMeasure(Math.abs(value), digits);
  if (value > 0) return `écart +${body}`;
  if (value < 0) return `écart −${body}`;
  return `écart ${body}`;
}

export function channelState(simulated, channel) {
  const list = Array.isArray(simulated) ? simulated : [];
  return list.includes(channel) ? "simulée" : "réelle";
}

export function heatWord(level) {
  if (level === 0) return "normale";
  if (level === 1) return "avertissement";
  if (level === 2) return "danger";
  return "non reçu";
}

export function heatTone(level) {
  if (level === 1) return "warning";
  if (level === 2) return "critical";
  return level === 0 ? "ok" : "muted";
}

export function gasAlertWord(flag) {
  if (flag === 1) return "élevé";
  if (flag === 0) return "normal";
  return "non reçu";
}

export function gasTone(flag) {
  if (flag === 1) return "warning";
  if (flag === 0) return "ok";
  return "muted";
}

export function lightDecision(dark) {
  if (dark === 1) return "Ouverture ou sabotage du boîtier";
  if (dark === 0) return "Claire";
  return "non reçu";
}

export function lightTone(dark) {
  if (dark === 1) return "warning";
  if (dark === 0) return "ok";
  return "muted";
}

export function lightWord(value) {
  if (value === 640) return "Claire";
  if (value === 80) return "Sombre";
  return "";
}

export function transitionsText(count) {
  if (!isNumber(count)) return "compte non reçu";
  const word = count === 1 ? "changement" : "changements";
  return `${formatLoose(count)} ${word} sur 1 min`;
}

export function modeWord(manual) {
  if (manual === 1) return "manuel";
  if (manual === 0) return "auto";
  return "non reçu";
}

export function rssiText(rssi) {
  if (!isNumber(rssi)) return "non reçu";
  return `${formatLoose(rssi)} dBm`;
}

export function uptimeText(seconds) {
  if (!isNumber(seconds)) return "non reçu";
  const minutes = Math.floor(seconds / 60);
  return `${formatLoose(minutes)} min`;
}

export function deviceWord(id) {
  if (id === BOARD_ID) return "boîtier";
  if (id === "camera") return "caméra";
  if (id === "esp01") return "simulateur";
  if (!id) return "appareil";
  return `appareil ${id}`;
}

export function capital(text) {
  if (!text) return "";
  return text.charAt(0).toLocaleUpperCase("fr-FR") + text.slice(1);
}

export function originTitle(alert) {
  if (!alert) return "Constat";
  if (alert.type === "gas_leak" || alert.message === "Pic de gaz simulé") return "Scénario";
  if (alert.type === "anomaly") return "Décision de l'IA capteurs";
  if (alert.type === "person") return "Décision de l'IA caméra";
  if (BOARD_TYPES.has(alert.type)) return "Décision de la carte";
  return "Constat";
}

export function severityWord(severity) {
  return SEVERITY[severity] || "";
}

export function trainedWord(value) {
  if (value === "simulator") return "appris sur le simulateur";
  if (value === "room") return "appris sur la salle";
  if (typeof value === "string" && value.trim()) return `appris sur ${value.trim()}`;
  return "";
}

export function modelCaption(alert) {
  const payload = alert?.payload;
  if (!payload || typeof payload !== "object") return null;
  const name = typeof payload.model_name === "string" ? payload.model_name.trim() : "";
  const detail = typeof payload.detail === "string" ? payload.detail.trim() : "";
  const version = typeof payload.version === "string" ? payload.version.trim() : "";
  const trained = trainedWord(payload.trained_on);
  const channels = Array.isArray(payload.channels)
    ? payload.channels.map((item) => CHANNEL[item] || "").filter(Boolean)
    : [];
  if (!name && !detail && !version && !trained && channels.length === 0) return null;
  return { name, detail, version, trained, channels };
}

export function modelMeta(caption) {
  if (!caption) return "";
  const parts = [];
  if (caption.version) parts.push(`version ${caption.version}`);
  if (caption.trained) parts.push(caption.trained);
  if (caption.channels.length) parts.push(caption.channels.join(", "));
  return parts.join(" · ");
}

export function cameraModelName(alert) {
  const stored = alert?.payload?.model;
  if (typeof stored === "string" && stored.trim()) return stored.trim();
  return "YOLOv8n";
}

function ackToken(alert) {
  const raw = alert?.payload?.ack;
  if (typeof raw === "string") {
    const text = raw.trim();
    const lower = text.toLowerCase();
    if (lower.startsWith("erreur:")) return { refused: true, token: "" };
    if (lower.startsWith("ok:")) return { refused: false, token: text.slice(3).trim() };
  }
  const message = typeof alert?.message === "string" ? alert.message : "";
  if (message.startsWith("Commande refusée")) return { refused: true, token: "" };
  const prefix = "Commande acceptée : ";
  if (message.startsWith(prefix)) return { refused: false, token: message.slice(prefix.length).trim() };
  return { refused: false, token: "" };
}

export function frenchAck(alert) {
  const { refused, token } = ackToken(alert);
  if (refused) return "Commande refusée";
  if (token && ACK[token]) return ACK[token];
  const lowered = token.toLowerCase();
  if (token && ACK[lowered]) return ACK[lowered];
  return "Commande acceptée";
}

export function splitAlerts(rows, limit = 20) {
  const findings = [];
  let ack = null;
  for (const row of rows || []) {
    if (row?.type === "ack") {
      if (!ack) ack = row;
      continue;
    }
    if (findings.length < limit) findings.push(row);
  }
  return { findings, ack };
}

export function gasPresentation(row) {
  if (!row) return { kind: "empty", state: "", figure: "", lines: [], alert: null };
  const simulated = channelState(row.simulated, "gas") === "simulée";
  const state = simulated ? "simulée" : "réelle";
  const ready = row.gas_ready;
  const raw = row.gas_raw;
  const keysMissing = ready == null && row.gas_delta == null && raw == null && row.alert_gas == null;

  if (keysMissing) {
    return {
      kind: "missing",
      state,
      figure: formatLoose(row.gas),
      lines: ["détail gaz non reçu"],
      alert: null,
    };
  }

  if (ready === 1 && !simulated) {
    const lines = ["compte analogique", formatDelta(row.gas_delta)];
    if (isNumber(raw)) lines.push(`lecture brute ${formatLoose(raw)}`);
    lines.push("Alerte de la carte à +400. Retour à +250.");
    return { kind: "real", state: "réelle", figure: formatLoose(row.gas), lines, alert: row.alert_gas };
  }

  if (ready === 0 && isNumber(raw)) {
    return {
      kind: "warmup",
      state: "en chauffe",
      figure: formatLoose(raw),
      lines: [
        "Préchauffage, 60 s",
        "lecture capteur",
        `Scénario : ${formatLoose(row.gas)}`,
        "Courbe : scénario",
      ],
      alert: null,
    };
  }

  if (simulated && raw == null) {
    return { kind: "simulated", state: "simulée", figure: formatLoose(row.gas), lines: [], alert: null };
  }

  return {
    kind: simulated ? "simulated" : "missing",
    state,
    figure: formatLoose(row.gas),
    lines: ready == null ? ["détail gaz non reçu"] : [],
    alert: null,
  };
}

export function modelCards(models) {
  if (!models || typeof models !== "object") return [];
  return MODEL_ROLES.map(([key, label]) => {
    const card = models[key];
    if (!card) return `${label} : non reçu`;
    if (!card.loaded) return `${label} : modèle absent`;
    const name = typeof card.name === "string" && card.name.trim() ? card.name.trim() : "nom non reçu";
    const extra = [card.version ? `version ${card.version}` : "", trainedWord(card.trained_on)].filter(Boolean);
    const tail = extra.length ? `, ${extra.join(", ")}` : "";
    return `${label} : ${name}${tail}`;
  });
}

export function mergeBoardReadings(current, incoming, boardId, max = 60) {
  const byId = new Map();
  for (const row of [...(current || []), ...(incoming || [])]) {
    if (!row || row.device !== boardId || row.id == null) continue;
    byId.set(row.id, row);
  }
  return [...byId.values()].sort((a, b) => a.ts - b.ts || a.id - b.id).slice(-max);
}

export function visitorLine(prefix, text) {
  if (typeof text !== "string" || !text.trim()) return "";
  const head = prefix ? `${prefix} — ` : "";
  return `${head}${text.trim()}`;
}
