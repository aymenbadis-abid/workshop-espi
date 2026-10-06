// Sentinel-X ESP32 firmware.
// Telemetry, retained status (with Last Will), plain commands, and ack.
// Temperature, humidity, and gas are simulated. Light is the real sensor.

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <PubSubClient.h>
#include <math.h>
#include <time.h>

#if __has_include("config.h")
#include "config.h"
#else
#error "Copy firmware/include/config.example.h to firmware/include/config.h"
#endif
#include "ca_cert.h"

#define PIN_SDA 21
#define PIN_SCL 22
#define PIN_LIGHT 34
#define PIN_BUZZER 25
#define PIN_LED_G 26
#define PIN_LED_R 27

#define READ_PERIOD_MS 200
#define STABLE_READS 3
#define SEND_PERIOD_MS 5000
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
bool displayReady = false;

bool isDark = false;
int candidate = -1;
int candidateCount = 0;
int lightValue = 0;
unsigned long eventTimes[MAX_EVENTS];
int eventCount = 0;
unsigned long lastRead = 0;
unsigned long lastSend = 0;
unsigned long lastBeep = 0;
unsigned long lastWifiTry = 0;
unsigned long lastMqttTry = 0;
bool sendNow = false;

// Manual override: -1 follows the light, 0 forced off, 1 forced on.
int ovRed = -1;
int ovGreen = -1;
int ovBuzzer = -1;

enum Scenario { SC_NORMAL, SC_DRIFT, SC_GAS };
Scenario scenario = SC_NORMAL;
float scenarioElapsed = 0;

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

int readLight() {
  int raw = analogRead(PIN_LIGHT);
  int scaled = raw * 1023 / 4095;
  if (LIGHT_INVERT) scaled = 1023 - scaled;
  if (scaled < 0) scaled = 0;
  if (scaled > 1023) scaled = 1023;
  return scaled;
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

void mqttLoop(unsigned long now) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (!mqtt.connected()) {
    if (now - lastMqttTry < 5000) return;
    lastMqttTry = now;
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
  lightValue = readLight();
  int dark = lightValue < LIGHT_DARK_BELOW ? 1 : 0;
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

void updateOutputs(unsigned long now) {
  bool red = (ovRed == -1) ? isDark : (ovRed == 1);
  bool green = (ovGreen == -1) ? !isDark : (ovGreen == 1);
  bool buzzer = (ovBuzzer == -1) ? isDark : (ovBuzzer == 1);
  digitalWrite(PIN_LED_R, red ? HIGH : LOW);
  digitalWrite(PIN_LED_G, green ? HIGH : LOW);
  unsigned long period = (ovBuzzer == 1) ? 800 : 2000;
  if (buzzer && now - lastBeep > period) {
    lastBeep = now;
    beep(2000, 120);
  }
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
  display.println(isDark ? "ALERTE" : "NORMAL");
  display.setTextSize(1);
  display.setCursor(0, 32);
  display.print("Lumiere: ");
  display.println(lightValue);
  display.print("Chgts/min: ");
  display.println(transitionsLastMinute(now));
  display.print("MQTT: ");
  display.print(mqtt.connected() ? "OK" : "KO");
  if (ovRed != -1 || ovGreen != -1 || ovBuzzer != -1) display.print("  MANUEL");
  display.print("  ");
  if (scenario == SC_DRIFT) display.print("derive");
  else if (scenario == SC_GAS) display.print("gaz");
  display.display();
}

void sendData(unsigned long now, float dt) {
  if (!mqtt.connected() || !clockReady()) return;
  if (dt < 0.2f) dt = 0.2f;
  if (dt > 30.0f) dt = 30.0f;
  float temp, hum, gas;
  sampleSimulated(dt, &temp, &hum, &gas);
  bool manual = ovRed != -1 || ovGreen != -1 || ovBuzzer != -1;
  int rssi = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
  char json[384];
  snprintf(json, sizeof(json),
           "{\"device\":\"%s\",\"ts\":%lu,\"temp\":%.2f,\"hum\":%.2f,\"gas\":%.1f,\"light\":%d,"
           "\"simulated\":[\"temp\",\"hum\",\"gas\"],\"light_dark\":%d,\"transitions_1min\":%d,"
           "\"manual\":%d,\"rssi\":%d}",
           DEVICE_ID, (unsigned long)time(nullptr), temp, hum, gas, lightValue,
           isDark ? 1 : 0, transitionsLastMinute(now), manual ? 1 : 0, rssi);
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
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_LIGHT, ADC_11db);

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
  mqtt.setBufferSize(512);
  mqtt.setSocketTimeout(4);
  Serial.println("Sentinel-X ESP32 started");
}

void loop() {
  unsigned long now = millis();
  if (now - lastRead >= READ_PERIOD_MS) {
    lastRead = now;
    readSensor(now);
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
