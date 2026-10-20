# esp8266 : indicateur LED de l'authentification biométrique

Firmware de l'ESP8266 qui reflète l'état de l'authentification du back-office sur une **LED bicolore (rouge/vert)**. Il interroge (poll) la passerelle du PC Hôte et joue le motif correspondant.

**IDE imposé : JetBrains CLion + PlatformIO** (plugin PlatformIO pour CLion). La carte par défaut est une NodeMCU v2 (ESP-12E).

## Câblage (par défaut)

| LED | Broche NodeMCU | GPIO |
|---|---|---|
| Vert | `D1` | GPIO5 |
| Rouge | `D2` | GPIO4 |

LED bicolore à cathode commune : chaque anode sur sa broche via une résistance (~220 Ω), cathode au GND. Adapter `PIN_GREEN` / `PIN_RED` dans `src/main.cpp` si besoin.

## États (consigne additionnelle 1)

| État reçu | LED |
|---|---|
| `off` | éteinte |
| `green_blink` | vert clignotant (en attente du mot de passe), continu |
| `green_solid` | vert fixe 30 s puis éteinte (mot de passe correct) |
| `red_blink` | rouge clignote 10× puis éteinte (mot de passe faux) |
| `red_solid` | rouge fixe 30 s puis éteinte (visage non reconnu) |

L'ESP ne rejoue un motif que lorsque le numéro de séquence (`seq`) change : un même état interrogé en boucle n'est joué qu'une fois.

## Compiler et flasher

1. Ouvrir `biometrics/esp8266/` dans **CLion** (plugin PlatformIO) ou en ligne de commande PlatformIO.
2. Copier `include/secrets.h.example` en `include/secrets.h` (ignoré par Git) et renseigner :
   - `WIFI_SSID`, `WIFI_PASSWORD` (point d'accès `RESILIENCE-G16`) ;
   - `GATEWAY_LED_URL` (ex. `http://192.168.137.1:8700/led`).
3. Compiler : `pio run`. Flasher (carte branchée) : `pio run -t upload`. Moniteur série : `pio device monitor` (115200 bauds).

Compilation vérifiée (`pio run`) : build OK, Flash ~28 %, RAM ~35 %. Le flashage et le WiFi se testent avec la carte.
