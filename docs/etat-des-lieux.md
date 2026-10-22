# État des lieux du projet

> Mis à jour le 22 octobre 2026 (revue complète : tests, calibrage, README). À tenir à jour à chaque PR importante.
> Échéances : gel du code **jeudi 17h**, dépôt des livrables **jeudi 23h59**.
> **Consigne additionnelle 1 (20/10)** : authentification du back-office par reconnaissance faciale + ESP8266 (POC logiciel fait, matériel à tester). Voir `biometrics/`.

## En résumé

**Avancement estimé : environ 69 %.** Toute la plateforme est codée, testée et documentée, et la **boucle de reprise autonome est prouvée en conteneurs** (arrêt de `payment-api`, reprise sans intervention humaine, transaction de contrôle réussie).
Reste à **calibrer le DoS sur le réseau du groupe** pour que la détection ML déclenche la boucle sur une vraie attaque, puis les livrables.

| Bloc | Poids estimé | Avancement | Contribution |
|---|---|---|---|
| Infrastructure et observabilité | 15 % | 90 % | 13,5 % |
| Services métier, frontal, dashboard | 15 % | 90 % | 13,5 % |
| Cybersécurité (WAF, Vault, SOC, attaques) | 15 % | 75 % | 11 % |
| IA (détection, assistant RAG) | 15 % | 75 % | 11 % |
| Remédiation et boucle de reprise | 15 % | 75 % | 11 % |
| Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | 10 % | 80 % | 8 % |
| Livrables (dossier, présentation, clip) | 15 % | 0 % | 0 % |
| **Total** | | | **environ 69 %** |

Les poids sont une estimation de l'équipe, pas le barème officiel.

---

## Tester le projet sur n'importe quel PC

```bash
python tests/run_all.py                 # tous les tests (Python 3.11+, Node.js 22 pour le front)
python tests/run_all.py --python-only   # sans Node.js
```

Aucun Docker ni service démarré n'est nécessaire : le script installe les dépendances dans `.venv-tests/` (ignoré par Git) et reproduit la CI. **11 suites, 140 tests, toutes vertes** le 22/10 sous Windows. Détail par suite : [README, section 14](../README.md#14-tests).

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
| Tests et calibrage (22/10) | Lanceur `tests/run_all.py` (tous les PC), tests du garde-fou d'attaque et du scénario e2e, correction du scénario e2e et de la feature `canary_up` du détecteur, revue du calibrage ([`calibrage-attaque-dos.md`](test-results/calibrage-attaque-dos.md)), README mis à jour | `chore/etat-tests-docs` |

Vérifié au runtime : 17 conteneurs `healthy` (stack complète), secrets lus depuis Vault, attaques bloquées au WAF, ban puis levée du ban sans coupure du canary, transaction `COMPLETED` depuis le navigateur et en ligne de commande, logs de tous les services dans Loki, boucle de reprise autonome.

---

## Ce qu'il reste à faire

### Priorité 1 : la démonstration sur le réseau du groupe

| Tâche | Détail | Pilier |
|---|---|---|
| Calibrer le DoS | Sur `RESILIENCE-G16`, relâcher `FRONTEND_API_RATE_LIMIT` et lancer `resilience_scenario.py` (flood authentifié par défaut) jusqu'à une **vraie dégradation** : un flood absorbé par les rate-limits ne fait pas dépasser le seuil ML (mesures dans [`calibrage-attaque-dos.md`](test-results/calibrage-attaque-dos.md)). Noter les réglages retenus | cyber, ia, infra |
| IP réelle au WAF | Vérifier depuis le PC Attaquant l'IP vue par le WAF (passerelle Docker attendue). Un ban coupe alors tout l'externe 5 min : à annoncer au jury | cyber, infra |
| Répétition générale | Stack complète, PC Attaquant, scénario de bout en bout, dashboard et Grafana affichés : chronométrer pour le clip de 60 s | tous |

### Priorité 2 : essais restants

| Tâche | Détail | Pilier |
|---|---|---|
| Assistant RAG en vrai | `ollama pull llama3.1:8b` et `ollama pull nomic-embed-text`, puis poser des questions sur les runbooks | ia |
| Biométrie matérielle | Caméra USB et ESP8266 branchés, enrôlement puis accès au back-office | cyber |
| Passerelle biométrique | Elle écoute sur `0.0.0.0` (README de `biometrics/gateway`), alors que le PC est aussi sur le WiFi du campus. Limiter par une règle du pare-feu Windows au point d'accès, ou lier à `192.168.137.1` après avoir vérifié que le dashboard la joint encore | cyber |
| Vérification mobile | Frontal et dashboard sur téléphone | dev |
| Modèle ML entraîné | Optionnel : `ml/training/collect.py` sous trafic nominal puis `train.py`, pour remplacer le modèle de repli synthétique | ia |

### Priorité 3 : livrables (jeudi)

| Livrable | Contenu |
|---|---|
| `Workshop2026-M2-G16-Dossier.pdf` | Dossier d'ingénierie et de gouvernance, 8 à 12 pages |
| `Workshop2026-M2-G16-Pres.pptx` | Présentation de 5 minutes |
| `Workshop2026-M2-G16-VidChrono.mp4` | Clip Chrono de 60 secondes, plan continu |
| `Workshop2026-M2-G16-Code.zip` | Tag `v1.0-freeze` à 17h, puis `git archive` (README, section 16) |

### Ménage et organisation

- **Protéger `main`** sur GitHub (1 approbation obligatoire, CI requise) : les PR sont pour l'instant mergées sans review.
- Remplir la section **Contributions** du README à partir de l'historique Git avant le rendu.
- `ml/notebooks/` n'existe pas : le README n'y renvoie plus. À créer seulement si l'équipe veut montrer l'exploration des données.

---

## Limites connues et points de vigilance

- **HTTPS** hors périmètre du laboratoire (pas de domaine ni de certificat) : documenté comme limite.
- **Droits sur les comptes** : tout utilisateur connecté peut débiter n'importe quel compte de démonstration.
- **IP réelle masquée par Docker Desktop** : le WAF voit la passerelle Docker pour tout le trafic externe. Un ban coupe donc tout l'externe pendant sa durée ; le canary interne n'est pas touché.
- **Détection ML** : avec le modèle de repli, seule une dégradation réelle (plusieurs indicateurs ensemble) dépasse le seuil ; un canari en échec seul donne 0,63. Une panne franche reste couverte par l'alerte Prometheus `TargetDown`.
- **WAF sur `192.168.137.1`** : si le point d'accès n'est pas actif avant Docker, le WAF reste à l'état `Created`. En développement : `WAF_BIND_IP=127.0.0.1` (le scénario e2e, lui, exige le point d'accès : le garde-fou refuse `127.0.0.1`).
- **Règle CRS 920350 exclue** (Host en adresse IP) : justifié dans `security/waf/crs-exclusions.conf`.
- **npm 10** (fourni avec Node 22) plante sur les dépendances de vitest 5 : npm 11.21.0 est épinglé dans les Dockerfile, la CI et `tests/run_all.py`.
- **PowerShell 5.1** abîme les guillemets imbriqués passés à un programme externe : préférer des scripts versionnés (exemple : `tests/e2e/transaction_curl.sh`).
