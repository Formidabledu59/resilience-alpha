# biometric-gateway : passerelle biométrique (service natif du PC Hôte)

Service Python (FastAPI) qui possède la caméra USB et la reconnaissance faciale, gère les habilitations, applique la logique d'essais / blocage et expose l'état de la LED. Tourne **en natif sur le PC Hôte** (hors Docker), car Docker Desktop n'accède pas à la caméra USB.

## Lancer

```powershell
cd biometrics/gateway
py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# BIO_CAMERA_INDEX : 0 = première caméra USB. BIND 0.0.0.0 pour que l'ESP puisse interroger.
$env:BIO_DATA_DIR = "$PWD\data"
python -m uvicorn app:app --host 0.0.0.0 --port 8700
```

> `--host 0.0.0.0` est nécessaire pour que l'ESP8266 (sur le point d'accès) et le dashboard (via `host.docker.internal`) joignent la passerelle. Pour durcir, lier à l'IP du point d'accès (`192.168.137.1`) plutôt que `0.0.0.0`.

| Variable | Rôle | Défaut |
|---|---|---|
| `BIO_DATA_DIR` | Dossier des visages et des mots de passe (local, hors dépôt) | `./data` |
| `BIO_CAMERA_INDEX` | Index de la caméra USB | `0` |
| `BIO_ENROLL_SAMPLES` | Nombre d'images capturées à l'enrôlement | `5` |
| `BIO_THRESHOLD` | Seuil de distance LBPH (plus bas = plus strict) | `70` |

## Endpoints

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/health` | Vivant |
| GET | `/led` | État de la LED `{seq, state}` (interrogé par l'ESP8266) |
| POST | `/identify` `{username}` | Étape 1 : caméra + reconnaissance faciale |
| POST | `/password` `{username, password}` | Étape 2 : mot de passe (après visage reconnu) |
| GET | `/users` | Habilitations : utilisateurs enrôlés |
| POST | `/enroll` `{username, password}` | Enrôle un visage (capture caméra) + mot de passe |
| DELETE | `/users/{username}` | Révoque une habilitation |

États de LED renvoyés par `/led` : `off`, `green_blink`, `green_solid`, `red_blink`, `red_solid`.

## Modules

| Fichier | Rôle | Testé |
|---|---|---|
| `auth_flow.py` | Machine à états (identifiant -> visage -> mot de passe), blocage, LED | ✓ (logique pure) |
| `recognizer.py` | Reconnaissance LBPH + stockage des visages | ✓ (images synthétiques) |
| `store.py` | Mots de passe hachés (PBKDF2) | ✓ (via l'app) |
| `faces.py` | Caméra USB + détection de visage (Haar) | caméra requise |
| `app.py` | API FastAPI | ✓ (caméra injectée) |

## Tests

```powershell
pip install -r requirements.txt pytest
pytest
```

Les tests n'utilisent pas la caméra (la capture est injectée, les visages sont synthétiques) : ils couvrent la machine à états, la reconnaissance, le blocage et le flux HTTP complet. La précision réelle de la reconnaissance se valide avec la caméra, sur le PC Hôte.
