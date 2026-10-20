"""Machine à états de l'authentification biométrique du back-office.

Flux : identifiant -> reconnaissance faciale -> mot de passe. Pilote aussi l'état de la
LED que l'ESP8266 va interroger (poll). Logique pure, sans caméra ni réseau : testable.

Règles (consigne additionnelle 1) :
  - identifiant saisi, visage reconnu   -> LED vert clignotant, saisie du mot de passe ;
  - mot de passe correct                -> LED vert fixe 30 s puis éteinte, accès accordé ;
  - mot de passe faux                   -> LED rouge clignote 10x, on recommence tout ;
  - visage non reconnu                  -> LED rouge fixe 30 s ; 1 nouvel essai puis blocage 5 min.
"""

import time

# États de LED envoyés à l'ESP. Les motifs temporisés (solid/blink) sont joués par l'ESP
# lui-même quand le numéro de séquence change (il n'a pas besoin d'horloge côté passerelle).
LED_OFF = "off"
LED_GREEN_BLINK = "green_blink"      # continu, jusqu'à la saisie du mot de passe
LED_GREEN_SOLID = "green_solid"      # ponctuel : vert fixe 30 s
LED_RED_BLINK = "red_blink"          # ponctuel : rouge clignote 10x
LED_RED_SOLID = "red_solid"          # ponctuel : rouge fixe 30 s

MAX_FACE_ATTEMPTS = 2                 # 1 essai + 1 nouvel essai
LOCKOUT_SECONDS = 300                 # blocage 5 minutes


class AuthFlow:
    def __init__(self, clock=time.monotonic):
        self._now = clock
        self._led_seq = 0
        self._led_state = LED_OFF
        self._face_fails: dict[str, int] = {}
        self._lock_until: dict[str, float] = {}
        self._awaiting: dict[str, bool] = {}   # visage reconnu, en attente du mot de passe

    # --- LED (interrogée par l'ESP) ------------------------------------------
    def _set_led(self, state: str) -> None:
        self._led_seq += 1
        self._led_state = state

    def led(self) -> dict:
        return {"seq": self._led_seq, "state": self._led_state}

    def reset_led(self) -> None:
        if self._led_state != LED_OFF:
            self._set_led(LED_OFF)

    # --- Blocage -------------------------------------------------------------
    def is_locked(self, username: str) -> bool:
        until = self._lock_until.get(username)
        return until is not None and self._now() < until

    def lock_remaining(self, username: str) -> int:
        until = self._lock_until.get(username)
        return max(0, int(until - self._now())) if until else 0

    # --- Étape 1 : identifiant + reconnaissance ------------------------------
    def start_identification(self, username: str) -> dict:
        """Avant d'allumer la caméra : refuse si l'utilisateur est bloqué."""
        if self.is_locked(username):
            return {"status": "locked", "retry_in": self.lock_remaining(username)}
        return {"status": "camera_on"}

    def on_recognition(self, username: str, recognized: bool) -> dict:
        """Résultat de la reconnaissance faciale pour cet identifiant."""
        if self.is_locked(username):
            return {"status": "locked", "retry_in": self.lock_remaining(username)}
        if recognized:
            self._face_fails[username] = 0
            self._awaiting[username] = True
            self._set_led(LED_GREEN_BLINK)
            return {"status": "recognized"}

        # non reconnu : rouge fixe 30 s, on incrémente le compteur d'échecs
        self._awaiting[username] = False
        self._face_fails[username] = self._face_fails.get(username, 0) + 1
        self._set_led(LED_RED_SOLID)
        if self._face_fails[username] >= MAX_FACE_ATTEMPTS:
            self._lock_until[username] = self._now() + LOCKOUT_SECONDS
            self._face_fails[username] = 0
            return {"status": "locked", "retry_in": LOCKOUT_SECONDS}
        return {"status": "not_recognized", "attempts_left": MAX_FACE_ATTEMPTS - self._face_fails[username]}

    # --- Étape 2 : mot de passe ---------------------------------------------
    def submit_password(self, username: str, password_ok: bool) -> dict:
        """N'est valable que si le visage vient d'être reconnu (étape 1 réussie)."""
        if not self._awaiting.get(username):
            return {"status": "face_first"}   # il faut d'abord passer la reconnaissance
        self._awaiting[username] = False
        if password_ok:
            self._set_led(LED_GREEN_SOLID)
            return {"status": "granted"}
        # mot de passe faux : rouge clignote 10x, on recommence toute la phase
        self._set_led(LED_RED_BLINK)
        return {"status": "denied"}
