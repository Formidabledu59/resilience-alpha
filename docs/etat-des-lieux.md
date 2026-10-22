# État des lieux du projet

> Mis à jour le 22 octobre 2026 (revue complète : tests, calibrage, README). À tenir à jour à chaque PR importante.
> Échéances : gel du code **jeudi 17h**, dépôt des livrables **jeudi 23h59**.
> **Consigne additionnelle 1 (20/10)** : authentification du back-office par reconnaissance faciale + ESP8266 (POC logiciel fait, matériel à tester). Voir `biometrics/`.

## En résumé

**Avancement estimé : environ 76 %.** Toute la plateforme est codée, testée et documentée. **La boucle complète est démontrée sur une vraie attaque** (22/10) : DoS envoyé sur le WAF du point d'accès, **détection par le ML** entraîné sur du trafic réel, ban de l'attaquant et relance par Ansible, transaction de contrôle `COMPLETED`, en 37 à 75 s, **6 essais sur 6** ([répétition générale](test-results/repetition-generale.md)).
Reste : rejouer l'attaque depuis le **PC Attaquant**, tourner le Clip Chrono, puis les livrables.

| Bloc | Poids estimé | Avancement | Contribution |
|---|---|---|---|
| Infrastructure et observabilité | 15 % | 90 % | 13,5 % |
| Services métier, frontal, dashboard | 15 % | 90 % | 13,5 % |
| Cybersécurité (WAF, Vault, SOC, attaques) | 15 % | 85 % | 13 % |
| IA (détection, assistant RAG) | 15 % | 85 % | 13 % |
| Remédiation et boucle de reprise | 15 % | 95 % | 14 % |
| Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | 10 % | 90 % | 9 % |
| Livrables (dossier, présentation, clip) | 15 % | 0 % | 0 % |
| **Total** | | | **environ 76 %** |

Les poids sont une estimation de l'équipe, pas le barème officiel.

---

## Tester le projet sur n'importe quel PC

```bash
python tests/run_all.py                 # tous les tests (Python 3.11+, Node.js 22 pour le front)
python tests/run_all.py --python-only   # sans Node.js
```

Aucun Docker ni service démarré n'est nécessaire : le script installe les dépendances dans `.venv-tests/` (ignoré par Git) et reproduit la CI. **12 suites, 173 tests, toutes vertes** le 22/10 sous Windows. Détail par suite : [README, section 14](../README.md#14-tests).

---

## Ce qui est fait

| Sujet | Contenu | PR |
|---|---|---|
| Socle du dépôt | `CLAUDE.md`, topologie réseau (7 réseaux), `.gitignore`, `.gitattributes` (LF), CODEOWNERS, template de PR, CI (gitleaks, yamllint, pytest, front) | #1 |
| Compose et observabilité | 18 services, profiles, durcissement (non-root, read_only, cap_drop), deux socket-proxy, Prometheus, Alertmanager, Loki, Alloy, Grafana, procédure Windows | #3, #4 |
| Chaîne de paiement | Contrat d'API, `auth-service` (JWT), `payment-api` (Postgres, transaction atomique), `canary` (sonde et transaction de contrôle, passe par le WAF) | #5 |
| Frontal de paiement | Connexion, virement, soldes, pages RGPD et CGU, 404, SEO, accessibilité, anti-spam, rate-limit `/api` réglable | #6 |
| Dashboard de supervision | Phases Avant / Pendant / Remédiation / Après, chiffres clés, courbes, cibles, journal des incidents, transaction de contrôle, back-office biométrique | #6, #12 |
| WAF | ModSecurity + OWASP CRS (injection SQL, XSS, accès fichiers, Log4Shell, scanners), rate-limit, liste de ban rechargée à chaud, journaux JSON dans Loki | #8 |
| Vault | `jwt_secret` et `postgres_password` dans Vault (KV v2), init idempotent sans secret affiché, politique lecture seule | #10 |
| SOC | Règles Loki sur les blocages WAF et échecs de connexion, alertes vers Alertmanager puis remediation-engine ; `security/hardening.md` | #11 |
| Scripts d'attaque | `attack/dos/flood.py` (flood anonyme ou authentifié), `attack/sqli/inject.py` (injections bloquées), garde-fou commun refusant toute cible hors `192.168.137.0/24`. **20 tests** (22/10) | #9 |
| Détection ML | `ml-detector` : Isolation Forest sur 6 features Prometheus, score toutes les 5 s, alerte HMAC après 3 relevés au-dessus de 0,7, modèle de repli synthétique ; `ml/training/` pour entraîner sur des métriques réelles | #15 |
| Remédiation | `remediation-engine` : webhooks HMAC et bearer, incidents, preuves Prometheus + Loki, playbooks Ansible (ban / levée du ban, relance), vérification par transaction de contrôle, journal chaîné SHA-256, rapport Markdown | #13, #15 |
| **Boucle prouvée en Docker (21/10)** | Arrêt de `payment-api` -> alerte -> `restart_api.yml` -> canari nominal -> transaction de contrôle `COMPLETED` -> incident `CLOSED` en 67 s environ. Détail : [`repetition-boucle-reprise.md`](test-results/repetition-boucle-reprise.md) | #15 |
| Assistant RAG | Streamlit (`127.0.0.1:8501`), LangChain + Ollama natif, index automatique de `docs/`, lecture seule stricte | #16, #18 |
| Biométrie back-office (consigne add. 1) | **POC logiciel** : passerelle native (OpenCV LBPH, habilitations, blocage), firmware ESP8266 (compile), flux identifiant -> visage -> mot de passe dans le dashboard | #12, #14 |
| Gouvernance | EBIOS RM (5 ateliers), PCA/PRA (RTO/RPO, scénarios, risques résiduels), NIS2/DORA, runbooks RB1 à RB7. À relire par l'équipe | #17 |
| **Répétition générale (22/10)** | Point d'accès actif, modèle ML entraîné sur 20 min de trafic réel, calibrage automatique du DoS (`tests/e2e/calibrate_dos.py`), 4 séries chronométrées : **6/6** sur les deux dernières. 3 défauts trouvés et corrigés : vérification sur métriques antérieures au redémarrage (HTTP 502), réalertes ML en boucle, attaquant non banni quand les limites sont relâchées | `feat/infra-repetition-generale` |
| Revue face au sujet (22/10) | Vérification raccourcie (3 relevés du canari au lieu de 60 s, pour tenir le Clip Chrono), gouvernance complétée (impact métier d'un arrêt, RTO mesurés, choix de restauration, disponibilité ≠ compromission, applicabilité DORA, [arbitrages et recommandations](governance/recommandations.md)), affirmations non démontrées corrigées, section Contributions, résultats et limites du ML, check-list du jour J (`DEMARRAGE.md` §12) | `chore/revue-sujet` |
| Tests et calibrage (22/10) | Lanceur `tests/run_all.py` (tous les PC), tests du garde-fou d'attaque et du scénario e2e, correction du scénario e2e et de la feature `canary_up` du détecteur, revue du calibrage ([`calibrage-attaque-dos.md`](test-results/calibrage-attaque-dos.md)), README mis à jour | `chore/etat-tests-docs` |

Vérifié au runtime : 17 conteneurs `healthy` (stack complète), secrets lus depuis Vault, attaques bloquées au WAF, ban puis levée du ban sans coupure du canary, transaction `COMPLETED` depuis le navigateur et en ligne de commande, logs de tous les services dans Loki, boucle de reprise autonome.

---

## Ce qu'il reste à faire

### Priorité 1 : la démonstration sur le réseau du groupe

| Tâche | Détail | Pilier |
|---|---|---|
| Attaque depuis le PC Attaquant | Les essais du 22/10 partaient du PC Hôte. Rejouer depuis le PC Attaquant connecté à `RESILIENCE-G16` (`flood.py --auth demo --concurrency 200`), vérifier l'IP vue par le WAF (passerelle Docker attendue) et que la détection ML se déclenche toujours | cyber, infra |
| Valider le réglage de démonstration | Limites de débit relâchées (proposé, [`calibrage-attaque-dos.md`](test-results/calibrage-attaque-dos.md)) : décision d'équipe, et l'argument à donner au jury | tous |
| Clip Chrono | 3 essais sur 6 sous 60 s. PC Attaquant connecté (le point d'accès ne s'éteint plus), économie d'énergie désactivée, plusieurs prises en plan continu | tous |
| Modèle ML entraîné (fait le 22/10) | `ml/models/model.joblib` n'est pas versionné : sur le PC du jury, refaire `collect.py` (20 min) puis `train.py`, ou copier le fichier | ia |

### Priorité 2 : essais restants

| Tâche | Détail | Pilier |
|---|---|---|
| Assistant RAG en vrai | `ollama pull llama3.1:8b` et `ollama pull nomic-embed-text`, puis poser des questions sur les runbooks | ia |
| Biométrie matérielle | Caméra USB et ESP8266 branchés, enrôlement puis accès au back-office | cyber |
| Passerelle biométrique | Elle écoute sur `0.0.0.0` (README de `biometrics/gateway`), alors que le PC est aussi sur le WiFi du campus. Limiter par une règle du pare-feu Windows au point d'accès, ou lier à `192.168.137.1` après avoir vérifié que le dashboard la joint encore | cyber |
| Vérification mobile | Frontal et dashboard sur téléphone | dev |

### Priorité 3 : livrables (jeudi)

| Livrable | Contenu |
|---|---|
| `Workshop2026-M2-G16-Dossier.pdf` | Dossier d'ingénierie et de gouvernance, 8 à 12 pages |
| `Workshop2026-M2-G16-Pres.pptx` | Présentation de 5 minutes |
| `Workshop2026-M2-G16-VidChrono.mp4` | Clip Chrono de 60 secondes, plan continu |
| `Workshop2026-M2-G16-Code.zip` | Tag `v1.0-freeze` à 17h, puis `git archive` (README, section 16) |

### Ménage et organisation

- **Protéger `main`** sur GitHub (1 approbation obligatoire, CI requise) : les PR sont pour l'instant mergées sans review.
- **Contributions** (README §18) : relevé Git fait ; chaque membre complète sa colonne « autres contributions » (exigé par le sujet : contribution de chacun visible dans le dossier).
- `ml/notebooks/` n'existe pas : le README n'y renvoie plus. À créer seulement si l'équipe veut montrer l'exploration des données.

---

## Limites connues et points de vigilance

- **HTTPS** hors périmètre du laboratoire (pas de domaine ni de certificat) : documenté comme limite.
- **Droits sur les comptes** : tout utilisateur connecté peut débiter n'importe quel compte de démonstration.
- **IP réelle masquée par Docker Desktop** : le WAF voit la passerelle Docker pour tout le trafic externe. Un ban coupe donc tout l'externe pendant sa durée ; le canary interne n'est pas touché.
- **Détection ML** : seule une dégradation réelle (plusieurs indicateurs ensemble) dépasse le seuil ; un canari en échec seul donne 0,67. Une panne franche reste couverte par l'alerte Prometheus `TargetDown`. Aux limites de débit par défaut, l'attaque est absorbée et c'est le SOC qui bannit (le ML ne déclenche pas).
- **Point d'accès Windows** : il s'éteint après ~5 min sans appareil connecté (économie d'énergie), le WAF devient injoignable. Désactiver l'économie d'énergie avant la démonstration.
- **WAF sur `192.168.137.1`** : si le point d'accès n'est pas actif avant Docker, le WAF reste à l'état `Created`. En développement : `WAF_BIND_IP=127.0.0.1` (le scénario e2e, lui, exige le point d'accès : le garde-fou refuse `127.0.0.1`).
- **Règle CRS 920350 exclue** (Host en adresse IP) : justifié dans `security/waf/crs-exclusions.conf`.
- **npm 10** (fourni avec Node 22) plante sur les dépendances de vitest 5 : npm 11.21.0 est épinglé dans les Dockerfile, la CI et `tests/run_all.py`.
- **PowerShell 5.1** abîme les guillemets imbriqués passés à un programme externe : préférer des scripts versionnés (exemple : `tests/e2e/transaction_curl.sh`).
