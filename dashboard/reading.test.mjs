import assert from "node:assert/strict";
import test from "node:test";

import {
  cameraModelName,
  channelState,
  formatDelta,
  frenchAck,
  gasPresentation,
  heatWord,
  lightDecision,
  lightWord,
  modelCaption,
  originTitle,
  mergeBoardReadings,
  splitAlerts,
  transitionsText,
  TEMP_LIMIT_CAPTION,
} from "./src/reading.js";

test("température au-dessus de 33 avec alert_heat à 0 reste normale", () => {
  assert.equal(heatWord(0), "normale");
  assert.equal(heatWord(2), "danger");
  assert.equal(heatWord(null), "non reçu");
});

test("lumière : claire, sombre, réelle si absente de simulated", () => {
  assert.equal(lightWord(640), "Claire");
  assert.equal(lightWord(80), "Sombre");
  assert.equal(channelState(["temp", "hum", "gas"], "light"), "réelle");
  assert.equal(channelState(["light"], "light"), "simulée");
  assert.equal(lightDecision(1), "Ouverture ou sabotage du boîtier");
  assert.equal(lightDecision(0), "Claire");
  assert.equal(lightDecision(null), "non reçu");
  assert.equal(transitionsText(null), "compte non reçu");
  assert.equal(transitionsText(2), "2 changements sur 1 min");
});

test("gaz sans gas_ready n'invente pas un préchauffage", () => {
  const missing = gasPresentation({ gas: 300, simulated: ["gas"] });
  assert.equal(missing.kind, "missing");
  assert.equal(missing.state, "simulée");
  assert.ok(missing.lines.includes("détail gaz non reçu"));
  assert.equal(missing.lines.some((line) => line.includes("Préchauffage")), false);
  assert.equal(missing.lines.some((line) => line.includes("+400")), false);
});

test("gaz simulé sans lecture brute", () => {
  const simulated = gasPresentation({
    gas: 310.5,
    simulated: ["gas"],
    gas_ready: 0,
    gas_raw: null,
    gas_delta: null,
    alert_gas: 0,
  });
  assert.equal(simulated.kind, "simulated");
  assert.equal(simulated.lines.some((line) => line.includes("Préchauffage")), false);
});

test("préchauffage seulement si gas_ready vaut 0 et gas_raw est un nombre", () => {
  const warmup = gasPresentation({
    gas: 300,
    simulated: ["gas"],
    gas_ready: 0,
    gas_raw: 1510,
    gas_delta: null,
    alert_gas: 0,
  });
  assert.equal(warmup.kind, "warmup");
  assert.equal(warmup.state, "en chauffe");
  assert.match(warmup.figure, /1[\s\u202f\u00a0]?510/);
  assert.ok(warmup.lines.includes("Préchauffage, 60 s"));
  assert.ok(warmup.lines.some((line) => line.startsWith("Scénario")));
  assert.equal(warmup.lines.includes("Alerte de la carte à +400. Retour à +250."), false);
});

test("gaz réel : écart et limites de la carte", () => {
  const real = gasPresentation({
    gas: 1820,
    simulated: [],
    gas_ready: 1,
    gas_raw: 1833,
    gas_delta: 420,
    alert_gas: 1,
  });
  assert.equal(real.kind, "real");
  assert.equal(real.state, "réelle");
  assert.equal(formatDelta(420), "écart +420");
  assert.ok(real.lines.includes("écart +420"));
  assert.ok(real.lines.some((line) => line.includes("+400") && line.includes("+250")));
  assert.equal(real.alert, 1);
});

test("origines en français, sans code", () => {
  assert.equal(originTitle({ type: "heat", message: "Température élevée : salle serveurs" }), "Décision de la carte");
  assert.equal(originTitle({ type: "gas_leak", message: "Pic de gaz simulé" }), "Scénario");
  assert.equal(originTitle({ type: "anomaly", message: "Dérive détectée" }), "Décision de l'IA capteurs");
  assert.equal(originTitle({ type: "person", message: "Une personne est arrivée dans la salle" }), "Décision de l'IA caméra");
  for (const title of ["heat", "ml", "http", "mqtt", "anomaly", "person"]) {
    assert.equal(originTitle({ type: "heat", message: "x" }).includes(title), title === "heat" ? false : false);
  }
  assert.equal(originTitle({ type: "anomaly", message: "x" }).includes("ml"), false);
});

test("le nom du modèle vient du payload, pas d'un score inventé", () => {
  const named = modelCaption({
    payload: {
      model_name: "forêt d'isolation",
      detail: "Température moyenne 24.0 °C.",
      features: { temp_slope: 1 },
      version: "simulator-couple-1",
      trained_on: "simulator",
      channels: ["temp", "gas"],
    },
  });
  assert.equal(named.name, "forêt d'isolation");
  assert.equal(named.detail, "Température moyenne 24.0 °C.");
  assert.equal("score" in named, false);
  assert.equal("features" in named, false);
  assert.equal(modelCaption({ payload: { features: { temp_mean: 24 } } }), null);
  assert.equal(cameraModelName({ payload: { model: "YOLOv8n" } }), "YOLOv8n");
  assert.equal(cameraModelName({ payload: {} }), "YOLOv8n");
});

test("les accusés quittent les constats et perdent la commande brute", () => {
  const { findings, ack } = splitAlerts([
    { id: 2, type: "ack", message: "Commande acceptée : led_red:1", payload: { ack: "ok:led_red:1" } },
    { id: 1, type: "heat", message: "Température élevée : salle serveurs" },
  ]);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].type, "heat");
  const text = frenchAck(ack);
  assert.equal(text, "Voyant rouge allumé");
  assert.equal(text.includes("led_red"), false);
  assert.equal(frenchAck({ message: "Commande acceptée : scenario:drift", payload: {} }).includes("scenario:"), false);
  assert.equal(frenchAck({ message: "Commande refusée : buzzer:1", payload: { ack: "erreur:buzzer:1" } }), "Commande refusée");
  assert.equal(
    frenchAck({ message: "Commande acceptée : buzzer:1", payload: { ack: "ok:buzzer:1" } }),
    "Buzzer allumé",
  );
});

test("les mesures se recollent par id, de la plus ancienne à la plus récente", () => {
  const merged = mergeBoardReadings(
    [
      { id: 2, device: "esp32-01", ts: 20 },
      { id: 1, device: "esp32-01", ts: 10 },
    ],
    [
      { id: 2, device: "esp32-01", ts: 20, temp: 29 },
      { id: 3, device: "esp32-01", ts: 30 },
      { id: 9, device: "esp01", ts: 40 },
    ],
    "esp32-01",
    60,
  );
  assert.deepEqual(merged.map((row) => row.id), [1, 2, 3]);
  assert.equal(merged[1].temp, 29);
});

test("aucune phrase de conseil dans les libellés fixes", () => {
  const blob = `${TEMP_LIMIT_CAPTION} ${frenchAck({ message: "Commande acceptée : auto" })}`;
  assert.equal(/devriez|aérez|aérer|appelez|éteignez/i.test(blob), false);
});
