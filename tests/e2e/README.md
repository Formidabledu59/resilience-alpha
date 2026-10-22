# tests/e2e : tests de bout en bout

| Fichier | Rôle | État |
|---|---|---|
| `transaction_curl.sh` | Une transaction fictive complète : authentification, solde, virement, contrôle `COMPLETED` | Fait |
| `resilience_scenario.py` | Scénario complet : transaction, attaque, détection, remédiation, transaction de contrôle | Fait |

## transaction_curl.sh

Les API n'ont aucun port publié : le script tourne dans un conteneur `curl` jetable relié au réseau interne `app-net`. Depuis PowerShell, à la racine du dépôt, avec la chaîne de paiement démarrée :

```powershell
$pass = (Select-String -Path .env -Pattern '^AUTH_DEMO_PASSWORD=(.*)').Matches[0].Groups[1].Value
docker run --rm --network resilience-alpha_app-net -e PASS=$pass -v "${PWD}/tests/e2e:/e2e:ro" curlimages/curl:8.22.0 sh /e2e/transaction_curl.sh
```

Variables facultatives : `FROM` (défaut `ACC-001`), `TO` (défaut `ACC-002`), `AMOUNT` (défaut `10.50`).
Code de sortie 0 si la transaction est `COMPLETED`, 1 sinon (authentification refusée, solde insuffisant, service indisponible).

Pourquoi un fichier plutôt qu'une commande en ligne : Windows PowerShell 5.1 abîme les guillemets imbriqués passés à un programme externe et ajoute un BOM aux scripts envoyés par l'entrée standard. Un script monté en lecture seule évite ces deux pièges.

## resilience_scenario.py

Scénario complet, à lancer **sur le PC Hôte** : Prometheus (`127.0.0.1:9090`) et le dashboard (`127.0.0.1:5173`) ne sont publiés que sur `127.0.0.1`, injoignables depuis le PC Attaquant. Stack complète démarrée (`--profile app --profile security --profile ia --profile remediation`) et **point d'accès `RESILIENCE-G16` actif** : l'attaque vise le WAF sur `192.168.137.1`, le garde-fou de `flood.py` refuse toute autre cible (dont `127.0.0.1`).

```bash
pip install -r attack/requirements.txt
export ATTACK_PASSWORD='<mot de passe demo, voir .env du PC Hôte>'
python tests/e2e/resilience_scenario.py
```

Déroulé : (1) transaction métier nominale, (2) lancement de `attack/dos/flood.py` (cible contrôlée par le garde-fou), (3) attente qu'un incident s'ouvre puis se clôture (détection ML, remédiation, transaction de contrôle), (4) transaction métier finale. Code de sortie 0 si la boucle est prouvée.

Options : `--waf` (défaut `http://192.168.137.1`), `--prometheus`, `--dashboard`, `--attack-seconds` (défaut 90), `--concurrency` (défaut 200), `--auth` / `--no-auth` (flood authentifié par défaut, il charge vraiment la base), `--timeout` (défaut 300 s), `--poll-seconds` (défaut 5), `--ban-wait` (défaut 360 s).

Garde-fous du scénario :
- si `flood.py` s'arrête aussitôt (cible refusée, `ATTACK_PASSWORD` absent), le scénario échoue tout de suite au lieu d'attendre 5 minutes ;
- seuls les incidents ouverts **après** le lancement de l'attaque comptent : un incident clos lors d'un essai précédent ne donne pas un faux succès ;
- la remédiation peut bannir l'IP du client (derrière Docker Desktop, tout l'externe partage la même IP) : la transaction finale attend la levée du ban (`BAN_MINUTES`, 5 min) au lieu d'échouer sur un 403.

Tests unitaires de la logique du scénario (sans stack, réseau simulé) : `python tests/run_all.py --only e2e`.

> Si aucun incident ne se déclenche, l'attaque n'a pas assez dégradé le service : renforcer la charge et relâcher les rate-limits (voir `docs/test-results/calibrage-attaque-dos.md` et `attack/dos/README.md`).
