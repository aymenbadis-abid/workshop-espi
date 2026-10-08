// Sentinel-X ESP32 firmware.
// Telemetry, retained status (with Last Will), plain commands, and ack.
// Light is the LM393 module. Temperature and humidity come from the DHT22.
// Gas is the MQ module on GPIO 35 (analog, through a 10k/10k divider).

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <PubSubClient.h>
#include <math.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

#if __has_include("config.h")
#include "config.h"
#else
#error "Copy firmware/include/config.example.h to firmware/include/config.h"
#endif
#include "ca_cert.h"

#ifndef USE_DHT
#define USE_DHT 1
#endif
#if USE_DHT
#include <DHT.h>
#endif
#ifndef USE_GAS
#define USE_GAS 1
#endif

#define PIN_SDA 21
#define PIN_SCL 22
#define PIN_LIGHT 34
#define PIN_DHT 32
#define PIN_GAS 35
#define PIN_BUZZER 25
#define PIN_LED_G 26
#define PIN_LED_R 27
#define DHT_TYPE DHT22
#define DHT_PERIOD_MS 2000
// MQ warmup in clean air, then the reading becomes the baseline.
#define GAS_WARMUP_MS 60000UL
#define GAS_ALERT_DELTA 400
#define GAS_CLEAR_DELTA 250
#define GAS_SMOOTH 0.1f
// Server inlet air. Warning starts at 27 C. Danger starts at 33 C.
#define TEMP_WARN_C 27.0f
#define TEMP_WARN_CLEAR_C 25.0f
#define TEMP_DANGER_C 33.0f
#define TEMP_DANGER_CLEAR_C 31.0f

#define READ_PERIOD_MS 200
// Used only if the hotspot blocks NTP. Must stay after the broker certificate notBefore.
#ifndef BUILD_EPOCH
#define BUILD_EPOCH 1791365334L
#endif
#define STABLE_READS 3
// DHT updates every 2 s. Publish at that pace so the screen follows the sensor.
// The server keeps a 5 s grid for the room models.
#define SEND_PERIOD_MS 2000
#define WINDOW_MS 60000UL
#define MAX_EVENTS 40

#define T_TELEMETRY "sentinelx/" DEVICE_ID "/telemetry"
#define T_ALERTS "sentinelx/" DEVICE_ID "/alerts"
#define T_STATUS "sentinelx/" DEVICE_ID "/status"
#define T_CMD "sentinelx/" DEVICE_ID "/cmd"
#define T_ACK "sentinelx/" DEVICE_ID "/ack"

Adafruit_SSD1306 display(128, 64, &Wire, -1);
WiFiClientSecure netClient;
PubSubClient mqtt(netClient);
#if USE_DHT
DHT dht(PIN_DHT, DHT_TYPE);
#endif
bool displayReady = false;

bool isDark = false;
bool isGas = false;
bool gasReady = false;
float gasAvg = -1;
int gasBaseline = 0;
enum HeatLevel { HEAT_OK = 0, HEAT_WARN = 1, HEAT_DANGER = 2 };
HeatLevel heat = HEAT_OK;
float temperature = NAN;
float humidity = NAN;
int candidate = -1;
int candidateCount = 0;
int lightValue = 0;
unsigned long eventTimes[MAX_EVENTS];
int eventCount = 0;
unsigned long lastRead = 0;
unsigned long lastSend = 0;
unsigned long lastWifiTry = 0;
unsigned long lastMqttTry = 0;
unsigned long lastDht = 0;
bool sendNow = false;

// LEDs: -1 follows the alarm, 0 forced off, 1 forced on.
// Buzzer: -1 follows the room, 0 forced silent, 1 forced strong beep.
int ovRed = -1;
int ovGreen = -1;
int ovBuzzer = -1;
unsigned long lastBeep = 0;

enum Scenario { SC_NORMAL, SC_DRIFT, SC_GAS };
Scenario scenario = SC_NORMAL;
float scenarioElapsed = 0;

void addEvent(unsigned long now) {
  if (eventCount == MAX_EVENTS) {
    for (int i = 1; i < MAX_EVENTS; i++) eventTimes[i - 1] = eventTimes[i];
    eventCount--;
  }
  eventTimes[eventCount++] = now;
}

int transitionsLastMinute(unsigned long now) {
  int n = 0;
  for (int i = 0; i < eventCount; i++) {
    if (now - eventTimes[i] <= WINDOW_MS) n++;
  }
  return n;
}

bool clockReady() {
  return time(nullptr) > 1700000000;
}

bool alarmActive() { return isDark || heat != HEAT_OK || isGas; }

HeatLevel nextHeatLevel(float temp) {
  if (heat == HEAT_OK) {
    if (temp >= TEMP_DANGER_C) return HEAT_DANGER;
    if (temp >= TEMP_WARN_C) return HEAT_WARN;
    return HEAT_OK;
  }
  if (heat == HEAT_WARN) {
    if (temp >= TEMP_DANGER_C) return HEAT_DANGER;
    if (temp <= TEMP_WARN_CLEAR_C) return HEAT_OK;
    return HEAT_WARN;
  }
  if (temp <= TEMP_DANGER_CLEAR_C) {
    if (temp <= TEMP_WARN_CLEAR_C) return HEAT_OK;
    return HEAT_WARN;
  }
  return HEAT_DANGER;
}

int readLightLevel() {
  bool dark = digitalRead(PIN_LIGHT) == HIGH;
  if (LIGHT_INVERT) dark = !dark;
  return dark ? 1 : 0;
}

void publishAlert(const char *type, const char *message, const char *severity) {
  if (!mqtt.connected() || !clockReady()) return;
  char json[220];
  snprintf(json, sizeof(json),
           "{\"device\":\"%s\",\"ts\":%lu,\"type\":\"%s\",\"message\":\"%s\",\"severity\":\"%s\"}",
           DEVICE_ID, (unsigned long)time(nullptr), type, message, severity);
  mqtt.publish(T_ALERTS, json);
}

bool applyScenario(const String &name) {
  Scenario next = scenario;
  if (name == "normal" || name == "reset") next = SC_NORMAL;
  else if (name == "drift") next = SC_DRIFT;
  else if (name == "gas_leak") next = SC_GAS;
  else return false;
  bool enteredLeak = next == SC_GAS && scenario != SC_GAS;
  scenario = next;
  scenarioElapsed = 0;
  if (enteredLeak) {
    publishAlert("gas_leak", "Pic de gaz simulé", "critical");
  }
  return true;
}

void sampleSimulated(float dt, float *temp, float *hum, float *gas) {
  scenarioElapsed += dt;
  float t = scenarioElapsed;
  float noise = (random(-30, 31)) / 100.0f;
  float humNoise = (random(-40, 41)) / 100.0f;
  float gasNoise = (float)random(-4, 5);
  if (scenario == SC_DRIFT) {
    *temp = 24.0f + 0.02f * t + noise;
    *gas = 300.0f + 0.15f * t + gasNoise;
    *hum = 48.0f + 0.5f * sinf(t / 40.0f) + humNoise;
  } else if (scenario == SC_GAS) {
    *temp = 24.0f + 0.3f * sinf(t / 30.0f) + noise;
    *gas = 300.0f + 900.0f * (1.0f - expf(-t / 4.0f)) + gasNoise;
    *hum = 48.0f + humNoise;
  } else {
    *temp = 24.0f + 0.4f * sinf(t / 30.0f) + noise;
    *gas = 300.0f + 8.0f * sinf(t / 45.0f) + gasNoise;
    *hum = 48.0f + 1.5f * sinf(t / 50.0f) + humNoise;
  }
  if (*hum < 0) *hum = 0;
  if (*hum > 100) *hum = 100;
  if (*gas < 0) *gas = 0;
}

bool handlePlain(String s) {
  if (s == "auto") {
    ovRed = ovGreen = ovBuzzer = -1;
    return true;
  }
  if (s == "gas_cal") {
#if USE_GAS
    if (!gasReady) return false;
    gasBaseline = (int)gasAvg;
    isGas = false;
    return true;
#else
    return false;
#endif
  }
  if (s.startsWith("scenario:")) return applyScenario(s.substring(9));
  int sep = s.indexOf(':');
  if (sep < 0) return false;
  String key = s.substring(0, sep);
  String val = s.substring(sep + 1);
  int v = (val == "1") ? 1 : (val == "0") ? 0 : -2;
  if (v == -2) return false;
  if (key == "led_red") ovRed = v;
  else if (key == "led_green") ovGreen = v;
  else if (key == "buzzer") ovBuzzer = v;
  else return false;
  return true;
}

String jsonStringField(const String &s, const char *key) {
  String pattern = String("\"") + key + "\"";
  int at = s.indexOf(pattern);
  if (at < 0) return "";
  int colon = s.indexOf(':', at + pattern.length());
  if (colon < 0) return "";
  int q1 = s.indexOf('"', colon + 1);
  if (q1 < 0) return "";
  int q2 = s.indexOf('"', q1 + 1);
  if (q2 < 0) return "";
  return s.substring(q1 + 1, q2);
}

bool handleCommand(String s) {
  s.trim();
  s.toLowerCase();
  if (s.startsWith("{")) {
    String scenarioName = jsonStringField(s, "scenario");
    if (scenarioName.length()) return applyScenario(scenarioName);
    String target = jsonStringField(s, "target");
    String state = jsonStringField(s, "state");
    if (!target.length() || !state.length()) return false;
    String bit = (state == "on") ? "1" : (state == "off") ? "0" : "";
    if (!bit.length()) return false;
    return handlePlain(target + ":" + bit);
  }
  return handlePlain(s);
}

void onMessage(char *topic, byte *payload, unsigned int len) {
  (void)topic;
  String s;
  unsigned int n = len < 80 ? len : 80;
  for (unsigned int i = 0; i < n; i++) s += (char)payload[i];
  Serial.print("[CMD] ");
  Serial.println(s);
  bool ok = handleCommand(s);
  char ack[96];
  snprintf(ack, sizeof(ack), "%s:%s", ok ? "ok" : "erreur", s.c_str());
  mqtt.publish(T_ACK, ack);
  sendNow = true;
}

void publishStatus(bool online) {
  if (!mqtt.connected()) return;
  char ip[16] = "0.0.0.0";
  if (WiFi.status() == WL_CONNECTED) {
    IPAddress addr = WiFi.localIP();
    snprintf(ip, sizeof(ip), "%u.%u.%u.%u", addr[0], addr[1], addr[2], addr[3]);
  }
  char json[128];
  snprintf(json, sizeof(json),
           "{\"device\":\"%s\",\"online\":%s,\"ip\":\"%s\",\"uptime\":%lu}",
           DEVICE_ID, online ? "true" : "false", ip, millis() / 1000UL);
  mqtt.publish(T_STATUS, json, true);
}

void wifiLoop(unsigned long now) {
  if (WiFi.status() == WL_CONNECTED || now - lastWifiTry < 10000) return;
  lastWifiTry = now;
  Serial.println("[WIFI] connecting");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

bool clockReady(unsigned long now) {
  if (time(nullptr) > 1700000000L) return true;
  static unsigned long waitStart = 0;
  if (waitStart == 0) {
    waitStart = now;
    Serial.println("[TIME] waiting for NTP");
    return false;
  }
  if (now - waitStart < 12000) return false;
  timeval tv = {};
  tv.tv_sec = BUILD_EPOCH;
  settimeofday(&tv, nullptr);
  Serial.print("[TIME] NTP missing, clock set to ");
  Serial.println((unsigned long)time(nullptr));
  return time(nullptr) > 1700000000L;
}

void mqttLoop(unsigned long now) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (!mqtt.connected()) {
    if (!clockReady(now)) return;
    if (now - lastMqttTry < 5000) return;
    lastMqttTry = now;
    Serial.print("[TIME] ");
    Serial.println((unsigned long)time(nullptr));
    Serial.println("[MQTT] connecting");
    char will[80];
    snprintf(will, sizeof(will), "{\"device\":\"%s\",\"online\":false}", DEVICE_ID);
    if (mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASS, T_STATUS, 1, true, will)) {
      publishStatus(true);
      mqtt.subscribe(T_CMD, 1);
      Serial.println("[MQTT] connected");
    } else {
      Serial.print("[MQTT] failed, state=");
      Serial.println(mqtt.state());
    }
    return;
  }
  mqtt.loop();
}

void readSensor(unsigned long now) {
  int dark = readLightLevel();
  lightValue = dark ? 80 : 640;
  if (dark == candidate) candidateCount++;
  else {
    candidate = dark;
    candidateCount = 1;
  }
  if (candidateCount >= STABLE_READS && (candidate == 1) != isDark) {
    isDark = candidate == 1;
    addEvent(now);
    sendNow = true;
    Serial.println(isDark ? "[EVENT] dark" : "[EVENT] light");
    if (isDark) publishAlert("tamper", "Ouverture ou sabotage du boîtier", "warning");
  }
}

void readDht(unsigned long now) {
#if USE_DHT
  if (now - lastDht < DHT_PERIOD_MS) return;
  lastDht = now;
  float nextTemp = dht.readTemperature();
  float nextHum = dht.readHumidity();
  if (isnan(nextTemp) || isnan(nextHum)) {
    temperature = NAN;
    humidity = NAN;
    Serial.println("[DHT] read failed");
    return;
  }
  temperature = nextTemp;
  humidity = nextHum;
  Serial.print("[DHT] ok ");
  Serial.print(nextTemp, 1);
  Serial.print("C ");
  Serial.println(nextHum, 1);
  HeatLevel next = nextHeatLevel(nextTemp);
  if (next == heat) return;
  heat = next;
  sendNow = true;
  if (heat == HEAT_DANGER) {
    Serial.println("[EVENT] heat danger");
    publishAlert("heat", "Température critique : salle serveurs", "critical");
  } else if (heat == HEAT_WARN) {
    Serial.println("[EVENT] heat warning");
    publishAlert("heat", "Température élevée : salle serveurs", "warning");
  } else {
    Serial.println("[EVENT] temperature ok");
    publishAlert("heat", "Température revenue à la normale", "info");
  }
#endif
}

void readGas(unsigned long now) {
#if USE_GAS
  int raw = analogRead(PIN_GAS);
  if (gasAvg < 0) gasAvg = raw;
  else gasAvg = gasAvg * (1.0f - GAS_SMOOTH) + raw * GAS_SMOOTH;
  if (!gasReady) {
    if (now >= GAS_WARMUP_MS) {
      gasReady = true;
      gasBaseline = (int)gasAvg;
      Serial.print("[GAS] baseline ");
      Serial.println(gasBaseline);
    }
    return;
  }
  int delta = (int)gasAvg - gasBaseline;
  bool next = isGas;
  if (!isGas && delta >= GAS_ALERT_DELTA) next = true;
  if (isGas && delta <= GAS_CLEAR_DELTA) next = false;
  if (next == isGas) return;
  isGas = next;
  sendNow = true;
  if (isGas) {
    Serial.println("[EVENT] gas");
    publishAlert("gas", "Gaz élevé", "warning");
  } else {
    Serial.println("[EVENT] gas ok");
    publishAlert("gas", "Gaz revenu à la normale", "info");
  }
#endif
}

// Passive piezo: a steady level only clicks. A square wave is the beep.
void beep(int freq, int ms) {
  long period = 1000000L / freq;
  long cycles = (long)ms * 1000L / period;
  for (long i = 0; i < cycles; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delayMicroseconds(period / 2);
    digitalWrite(PIN_BUZZER, LOW);
    delayMicroseconds(period / 2);
  }
}

void updateOutputs(unsigned long now) {
  bool alarm = alarmActive();
  bool red = (ovRed == -1) ? alarm : (ovRed == 1);
  bool green = (ovGreen == -1) ? !alarm : (ovGreen == 1);
  digitalWrite(PIN_LED_R, red ? HIGH : LOW);
  digitalWrite(PIN_LED_G, green ? HIGH : LOW);

  bool strong = false;
  bool weak = false;
  if (ovBuzzer == 0) {
    digitalWrite(PIN_BUZZER, LOW);
    return;
  }
  if (ovBuzzer == 1) {
    strong = true;
  } else if (heat == HEAT_DANGER) {
    strong = true;
  } else if (heat == HEAT_WARN || isGas || isDark) {
    weak = true;
  }
  if (!strong && !weak) {
    digitalWrite(PIN_BUZZER, LOW);
    return;
  }
  // Danger: longer tone, close together. Warning: shorter tone, further apart.
  unsigned long period = strong ? 800 : 2000;
  int length = strong ? 160 : 70;
  if (now - lastBeep < period) return;
  lastBeep = now;
  beep(2000, length);
}

void drawScreen(unsigned long now) {
  if (!displayReady) return;
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("IP ");
    display.println(WiFi.localIP());
  } else {
    display.println("Wi-Fi : deconnecte");
  }
  display.setTextSize(2);
  display.setCursor(0, 12);
  display.println(alarmActive() ? "ALERTE" : "NORMAL");
  display.setTextSize(1);
  display.setCursor(0, 32);
  if (isnan(temperature)) display.println("T: --  H: --");
  else {
    display.print("T:");
    display.print(temperature, 1);
    display.print("C H:");
    display.print(humidity, 0);
    display.println("%");
  }
  display.print("Lum: ");
  display.print(isDark ? "SOMBRE" : "CLAIRE");
  display.print(" chg:");
  display.println(transitionsLastMinute(now));
  display.print("MQTT: ");
  display.print(mqtt.connected() ? "OK" : "KO");
  if (heat == HEAT_DANGER) display.print(" DANGER");
  else if (heat == HEAT_WARN) display.print(" CHAUD");
  if (isGas) display.print(" GAZ");
  if (ovRed != -1 || ovGreen != -1 || ovBuzzer != -1) display.print(" MAN");
  display.println();
#if USE_GAS
  if (gasAvg < 0) display.print("Gaz: --");
  else if (!gasReady) {
    unsigned long left = (GAS_WARMUP_MS > now) ? (GAS_WARMUP_MS - now) / 1000UL : 0;
    display.print("Gaz: chauffe ");
    display.print(left);
    display.print("s");
  } else {
    display.print("Gaz:");
    display.print((int)gasAvg);
    if (isGas) display.print(" ALERTE");
  }
#endif
  display.display();
}

void sendData(unsigned long now, float dt) {
  if (!mqtt.connected() || !clockReady()) return;
  if (dt < 0.2f) dt = 0.2f;
  if (dt > 30.0f) dt = 30.0f;
  float simTemp, simHum, simGas;
  sampleSimulated(dt, &simTemp, &simHum, &simGas);
  bool tempReal = !isnan(temperature);
  bool humReal = !isnan(humidity);
  bool gasReal = false;
#if USE_GAS
  gasReal = gasReady;
#endif
  float temp = tempReal ? temperature : simTemp;
  float hum = humReal ? humidity : simHum;
  float gas = gasReal ? gasAvg : simGas;
  bool manual = ovRed != -1 || ovGreen != -1 || ovBuzzer != -1;
  int rssi = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
  char simulated[64] = "";
  bool wrote = false;
  if (!tempReal) { strcat(simulated, "\"temp\""); wrote = true; }
  if (!humReal) {
    if (wrote) strcat(simulated, ",");
    strcat(simulated, "\"hum\"");
    wrote = true;
  }
  if (!gasReal) {
    if (wrote) strcat(simulated, ",");
    strcat(simulated, "\"gas\"");
  }
  char tempField[16];
  char humField[16];
  char gasRaw[16];
  char gasDelta[16];
  if (tempReal) snprintf(tempField, sizeof(tempField), "%.1f", temperature);
  else snprintf(tempField, sizeof(tempField), "null");
  if (humReal) snprintf(humField, sizeof(humField), "%.1f", humidity);
  else snprintf(humField, sizeof(humField), "null");
#if USE_GAS
  if (gasAvg < 0) snprintf(gasRaw, sizeof(gasRaw), "null");
  else snprintf(gasRaw, sizeof(gasRaw), "%d", (int)gasAvg);
  if (!gasReady) snprintf(gasDelta, sizeof(gasDelta), "null");
  else snprintf(gasDelta, sizeof(gasDelta), "%d", (int)gasAvg - gasBaseline);
#else
  snprintf(gasRaw, sizeof(gasRaw), "null");
  snprintf(gasDelta, sizeof(gasDelta), "null");
#endif
  char json[640];
  snprintf(json, sizeof(json),
           "{\"device\":\"%s\",\"ts\":%lu,\"temp\":%.2f,\"hum\":%.2f,\"gas\":%.1f,\"light\":%d,"
           "\"simulated\":[%s],\"temperature\":%s,\"humidity\":%s,\"gas_raw\":%s,\"gas_delta\":%s,"
           "\"gas_ready\":%d,\"light_dark\":%d,\"transitions_1min\":%d,\"alert_heat\":%d,"
           "\"alert_gas\":%d,\"manual\":%d,\"rssi\":%d}",
           DEVICE_ID, (unsigned long)time(nullptr), temp, hum, gas, lightValue, simulated,
           tempField, humField, gasRaw, gasDelta, gasReal ? 1 : 0, isDark ? 1 : 0,
           transitionsLastMinute(now), (int)heat, isGas ? 1 : 0, manual ? 1 : 0, rssi);
  Serial.println(json);
  mqtt.publish(T_TELEMETRY, json);
  publishStatus(true);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LIGHT, INPUT);
#if USE_GAS
  analogSetPinAttenuation(PIN_GAS, ADC_11db);
#endif
#if USE_DHT
  dht.begin();
#endif

  Wire.begin(PIN_SDA, PIN_SCL);
  displayReady = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!displayReady) Serial.println("[OLED] missing");

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  lastWifiTry = millis();
  configTime(0, 0, "pool.ntp.org", "time.google.com");

  netClient.setCACert(CA_CERT);
  netClient.setHandshakeTimeout(8);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(768);
  mqtt.setSocketTimeout(4);
  Serial.println("Sentinel-X ESP32 started");
}

void loop() {
  unsigned long now = millis();
  if (now - lastRead >= READ_PERIOD_MS) {
    lastRead = now;
    readSensor(now);
    readDht(now);
    readGas(now);
    updateOutputs(now);
    drawScreen(now);
  }
  if (sendNow || now - lastSend >= SEND_PERIOD_MS) {
    float dt = lastSend == 0 ? (SEND_PERIOD_MS / 1000.0f) : (now - lastSend) / 1000.0f;
    sendNow = false;
    lastSend = now;
    sendData(now, dt);
  }
  wifiLoop(now);
  mqttLoop(now);
}
