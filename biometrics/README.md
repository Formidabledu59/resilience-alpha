# biometrics : authentification biométrique du back-office

Réponse à la **consigne additionnelle 1** : renforcer l'accès au back-office (le dashboard de supervision) par de la **reconnaissance faciale** (caméra USB + IA légère sur le PC Hôte), avec l'état signalé par une **LED bicolore pilotée par un ESP8266**.

```
Navigateur (back-office)                 ESP8266 (LED rouge/verte, WiFi RESILIENCE-G16)
   │  identifiant / mot de passe              ▲  interroge GET /led (poll)
   ▼                                          │
Passerelle biométrique (gateway/) - service NATIF du PC Hôte, hors Docker
   ├─ caméra USB + reconnaissance faciale (OpenCV LBPH, « IA légère »)
   ├─ habilitations (visages + mots de passe)
   ├─ logique d'essais / blocage 5 min
   └─ expose l'état de la LED (/led)
```

| Dossier | Contenu |
|---|---|
| [`gateway/`](gateway/) | Passerelle Python (FastAPI) : caméra, reconnaissance, habilitations, machine à états, état LED. Tourne **en natif sur le PC Hôte**. |
| [`esp8266/`](esp8266/) | Firmware de l'ESP8266 (PlatformIO + CLion) : WiFi + LED bicolore qui reflète l'état. |

Le flux d'authentification est intégré au dashboard : [`services/dashboard/src/components/BackOfficeGate.jsx`](../services/dashboard/src/components/BackOfficeGate.jsx).

## Le flux (consigne additionnelle 1)

1. L'utilisateur saisit son **identifiant**.
2. La **caméra s'active**, la reconnaissance faciale vérifie l'identité :
   - **reconnu** : LED **vert clignotant**, la saisie du mot de passe est autorisée ;
   - **non reconnu** : LED **rouge fixe 30 s**, identifiant vidé, caméra éteinte. 1 nouvel essai, puis **blocage 5 min**.
3. Saisie du **mot de passe** :
   - **correct** : LED **vert fixe 30 s** puis éteinte, le back-office s'affiche ;
   - **faux** : LED **rouge clignote 10×**, on recommence toute l'identification.

## Pourquoi un service natif (hors Docker)

La caméra USB est un périphérique du PC Hôte ; Docker Desktop (Windows) n'y accède pas simplement, et la consigne impose la caméra **sur le PC Hôte**. La passerelle tourne donc en natif, comme Ollama. Le dashboard (dans Docker) la joint via `host.docker.internal` ; l'ESP la joint via l'IP du point d'accès (`192.168.137.1`).

## Démarrer (résumé)

1. Passerelle sur le PC Hôte : voir [`gateway/README.md`](gateway/README.md).
2. Enrôler un visage : dans le back-office, onglet **Habilitations**.
3. ESP8266 : flasher le firmware ([`esp8266/README.md`](esp8266/README.md)).

## Choix et limites (POC)

- **Reconnaissance** : OpenCV **LBPH**, la plus légère (« IA légère » de la consigne). Précision correcte en conditions maîtrisées (démo), moins robuste que des modèles lourds.
- **ESP** : il **interroge** la passerelle (poll) toutes les ~300 ms ; les motifs temporisés (30 s, 10 clignotements) sont joués en autonomie par l'ESP.
- **Tension avec CLAUDE.md** (« seul le WAF publie un port réseau ») : la passerelle est un service **natif de l'hôte**, pas un conteneur Docker. Elle écoute sur l'interface du point d'accès pour l'ESP. Exception assumée et documentée, propre à cette consigne.
- **Session back-office** : après acceptation, un drapeau de session est gardé côté navigateur (POC). Une vraie session serveur serait nécessaire en production.
- **Hors stack imposée** : OpenCV et le firmware ESP ne sont pas dans la stack initiale ; la consigne additionnelle les impose explicitement.
