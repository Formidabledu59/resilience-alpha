// ESP8266 : indicateur LED bicolore de l'authentification biométrique du back-office.
//
// Interroge (poll) la passerelle du PC Hote (GET /led) et reflete l'etat sur une LED
// rouge/verte, selon la consigne additionnelle 1 :
//   off           -> eteinte
//   green_blink   -> vert clignotant (en attente du mot de passe), continu
//   green_solid   -> vert fixe 30 s puis eteinte (mot de passe correct)
//   red_blink     -> rouge clignote 10x puis eteinte (mot de passe faux)
//   red_solid     -> rouge fixe 30 s puis eteinte (visage non reconnu)
//
// Les motifs temporises (solid / blink) sont des etats terminaux : on les joue en entier.
// Seul green_blink est continu et laisse le poll se poursuivre.

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

#include "secrets.h"

// Broches de la LED bicolore (NodeMCU : D1 = GPIO5, D2 = GPIO4).
static const uint8_t PIN_GREEN = D1;
static const uint8_t PIN_RED = D2;

static const unsigned long POLL_INTERVAL_MS = 300;
static const unsigned long BLINK_PERIOD_MS = 400;   // demi-periode du clignotement vert
static const unsigned long SOLID_MS = 30000;        // vert / rouge fixe : 30 s
static const int RED_BLINK_COUNT = 10;

static long lastSeq = -1;
static String currentState = "off";
static unsigned long lastPoll = 0;
static unsigned long lastBlink = 0;
static bool greenOn = false;

void setLed(bool green, bool red) {
  digitalWrite(PIN_GREEN, green ? HIGH : LOW);
  digitalWrite(PIN_RED, red ? HIGH : LOW);
}

// Motif terminal : on le joue en entier (delay() alimente la pile WiFi).
void playSolid(bool green) {
  setLed(green, !green);
  delay(SOLID_MS);
  setLed(false, false);
}

void playRedBlink() {
  for (int i = 0; i < RED_BLINK_COUNT; i++) {
    setLed(false, true);
    delay(250);
    setLed(false, false);
    delay(250);
  }
}

void applyState(const String &state) {
  currentState = state;
  greenOn = false;
  if (state == "green_solid") {
    playSolid(true);
    currentState = "off";
  } else if (state == "red_solid") {
    playSolid(false);
    currentState = "off";
  } else if (state == "red_blink") {
    playRedBlink();
    currentState = "off";
  } else if (state == "off") {
    setLed(false, false);
  }
  // green_blink : gere dans loop()
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
  }
}

void pollLed() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
    return;
  }
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, GATEWAY_LED_URL)) {
    return;
  }
  int code = http.GET();
  if (code == HTTP_CODE_OK) {
    JsonDocument doc;
    if (deserializeJson(doc, http.getString()) == DeserializationError::Ok) {
      long seq = doc["seq"] | -1;
      String state = doc["state"] | "off";
      if (seq != lastSeq) {         // ne (re)joue un etat que sur changement de sequence
        lastSeq = seq;
        applyState(state);
      }
    }
  }
  http.end();
}

void setup() {
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  setLed(false, false);
  Serial.begin(115200);
  connectWifi();
}

void loop() {
  unsigned long now = millis();

  if (now - lastPoll >= POLL_INTERVAL_MS) {
    lastPoll = now;
    pollLed();
  }

  // Clignotement vert continu, non bloquant, pendant l'attente du mot de passe
  if (currentState == "green_blink" && now - lastBlink >= BLINK_PERIOD_MS) {
    lastBlink = now;
    greenOn = !greenOn;
    setLed(greenOn, false);
  }
}
