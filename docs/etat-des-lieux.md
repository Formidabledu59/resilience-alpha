# État des lieux du projet

> Mis à jour le 20 octobre 2026, avec Vault (branche `feat/cyber-vault`). À tenir à jour à chaque PR importante.
> Échéances : gel du code **jeudi 17h**, dépôt des livrables **jeudi 23h59**.
> **Consigne additionnelle 1 (20/10)** : authentification du back-office par reconnaissance faciale + ESP8266 (POC logiciel fait, matériel à tester). Voir [[exigence-biometrie-esp8266]] et `biometrics/`.

## En résumé

**Avancement estimé : environ 40 %.** La fondation est en place et vérifiée : infrastructure, observabilité, chaîne de paiement, frontal, dashboard, WAF, Vault et SOC.
Reste le **coeur de la démonstration** : attaque, détection ML et remédiation automatique, puis la gouvernance et les livrables.

| Bloc | Poids estimé | Avancement | Contribution |
|---|---|---|---|
| Infrastructure et observabilité | 15 % | 90 % | 13,5 % |
| Services métier, frontal, dashboard | 15 % | 90 % | 13,5 % |
| Cybersécurité (WAF, Vault, SOC, attaques) | 15 % | 70 % | 10,5 % |
| IA (détection, assistant RAG) | 15 % | 0 % | 0 % |
| Remédiation et boucle de reprise | 15 % | 10 % | 1,5 % |
| Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | 10 % | 10 % | 1 % |
| Livrables (dossier, présentation, clip) | 15 % | 0 % | 0 % |
| **Total** | | | **environ 40 %** |

Les poids sont une estimation de l'équipe, pas le barème officiel.

---

## Ce qui est fait

| Sujet | Contenu | PR |
|---|---|---|
| Socle du dépôt | `CLAUDE.md`, topologie réseau corrigée (7 réseaux), `.gitignore`, `.gitattributes` (LF), CODEOWNERS, template de PR, CI (gitleaks, yamllint, pytest) | #1 |
| Compose et observabilité | 18 services déclarés, profiles, durcissement (non-root, read_only, cap_drop), deux socket-proxy, Prometheus, Alertmanager, Loki, Alloy, Grafana, procédure Windows | #3 |
| Correctifs d'observabilité | Démarrage d'Alertmanager (secret Compose), découverte des logs par Alloy | #4 |
| Chaîne de paiement | Contrat d'API, `auth-service` (JWT), `payment-api` (Postgres, transaction atomique), `canary` (sonde et transaction de contrôle), 11 tests | #5 |
| Frontal de paiement | Connexion, virement, soldes, pages RGPD et CGU, 404, SEO, accessibilité, anti-spam, mesure d'audience sans cookie, 12 tests | #6 |
| Dashboard de supervision | Phases Avant / Pendant / Remédiation / Après, chiffres clés, courbes, cibles, incidents, transaction de contrôle, 11 tests | #6 |
| WAF | ModSecurity + OWASP CRS (injection SQL, XSS, accès fichiers, Log4Shell, scanners bloqués), rate-limit, liste de ban rechargée à chaud, journaux JSON dans Loki, canary passant par le WAF | `feat/cyber-waf` |
| Vault | Secrets `jwt_secret` et `postgres_password` dans Vault (KV v2), init idempotent sans secret affiché, politique lecture seule + token de service, lus par auth-service et payment-api | `feat/cyber-vault` |
| SOC | Règles de détection (ruler Loki) sur les blocages WAF et échecs de connexion, alertes vers Alertmanager (vérifié : inactive -> pending -> firing) ; `security/hardening.md` | `feat/cyber-soc` |
| Biométrie back-office (consigne add. 1) | **POC logiciel** : passerelle native (OpenCV LBPH, habilitations, blocage), firmware ESP8266 (compile OK), flux identifiant→visage→mot de passe dans le dashboard. 33 tests. Matériel (caméra, ESP) à tester | `feat/cyber-biometrie` |
| Grafana | Dashboards « Vue globale » et « Frontal et sécurité » (dont blocages WAF et règles déclenchées) | #3, #6, `feat/cyber-waf` |
| CI | 5 jobs verts : gitleaks, yamllint, pytest, front (frontend), front (dashboard) | #1, #6 |
| Documentation | README, `infra/README.md`, `docs/architecture/contracts.md`, README de chaque service développé, procédure d'utilisation | toutes |

Vérifié au runtime : 14 conteneurs `healthy` (profiles app + security), secrets `jwt_secret` et `postgres_password` lus depuis Vault (transaction COMPLETED), attaques bloquées au WAF, ban puis levée du ban sans coupure du canary, transaction `COMPLETED` depuis le navigateur et en ligne de commande, `canary_up = 1`, logs de tous les services dans Loki, aucune adresse IP dans les journaux du frontal.

---

## Ce qu'il reste à faire

### Priorité 1 : la boucle de démonstration (attaque, détection, remédiation, preuve)

| Tâche | Détail | Pilier |
|---|---|---|
| IP réelle au WAF | Vérifier depuis le PC Attaquant (point d'accès actif) quelle IP voit le WAF : passerelle Docker ou IP réelle. Voir `security/waf/README.md` | cyber, infra |
| Attaque DoS | `attack/dos/` : cible en paramètre, refus de toute cible hors `192.168.137.0/24`. À calibrer pour **dégrader réellement** payment-api malgré le rate-limit du WAF (`WAF_RATE_LIMIT`) et du frontal, sinon il n'y a pas d'incident à détecter | cyber |
| Détecteur ML | Collecte des métriques sous trafic nominal, entraînement Isolation Forest (`ml/training/`), service `ml/detector` (score toutes les 5 s, `ml_anomaly_score` et `ml_anomaly_threshold` dans `/metrics`, webhook signé HMAC) | ia |
| Moteur de remédiation | Webhooks HMAC (ml-detector) et bearer (Alertmanager), liste blanche de playbooks, `GET /incidents` (contrat dans `contracts.md`), journalisation dans Loki | infra, dev |
| Playbooks Ansible | `ban_ip.yml` (contrat de ban dans `contracts.md` : fichier dans `waf-banlist`, puis `HUP` via socket-proxy-rw, ban temporaire), `restart_api.yml`, `verify.yml` (attend `canary_up == 1` puis `POST /probe`). Permissions du volume `waf-banlist` à régler pour l'utilisateur 10001 | infra |
| Scénario de bout en bout | `tests/e2e/resilience_scenario.py`, puis répétition réelle depuis le PC Attaquant | dev, infra |

### Priorité 2 : compléter le visible et la sécurité

| Tâche | Détail | Pilier |
|---|---|---|
| ~~Règles SOC~~ | **Fait** (`feat/cyber-soc`) : ruler Loki + Alertmanager | cyber |
| Scénario d'injection | `attack/sqli/` : script de démonstration (le blocage par le WAF fonctionne déjà, règle 942100) | cyber |
| ~~Vault~~ | **Fait** (`feat/cyber-vault`) : `config.hcl`, `init.sh` idempotent sans secret affiché, `jwt_secret` et `postgres_password` lus depuis Vault par auth-service et payment-api, repli sur l'env pour le profile app seul | cyber |
| ~~Durcissement documenté~~ | **Fait** (`feat/cyber-soc`) : `security/hardening.md` | cyber |
| Vérification mobile | Contrôle à la main du frontal et du dashboard sur téléphone | dev |

### Priorité 3 : reste du sujet

| Tâche | Détail | Pilier |
|---|---|---|
| Assistant RAG | Ollama natif (8B maximum) + LangChain, lecture seule de `docs/`, et `assistant-rag/README.md` (lien déjà présent dans le README) | ia |
| Gouvernance | EBIOS RM, PCA/PRA (scénarios, RTO/RPO, risques résiduels), analyse NIS2/DORA | gouv |
| Runbooks et résultats d'essais | `docs/runbooks/`, `docs/test-results/` | gouv |
| Notebooks ML | `ml/notebooks/`, `ml/README.md` (données, résultats, limites). Ces deux chemins sont déjà liés depuis le README : liens cassés tant qu'ils n'existent pas | ia |

### Priorité 4 : livrables (jeudi)

| Livrable | Contenu |
|---|---|
| `Workshop2026-M2-G16-Dossier.pdf` | Dossier d'ingénierie et de gouvernance, 8 à 12 pages |
| `Workshop2026-M2-G16-Pres.pptx` | Présentation de 5 minutes |
| `Workshop2026-M2-G16-VidChrono.mp4` | Clip Chrono de 60 secondes, plan continu |
| `Workshop2026-M2-G16-Code.zip` | Tag `v1.0-freeze` à 17h, puis `git archive` (README, section 16) |

### Ménage et organisation

- **Protéger `main`** sur GitHub (1 approbation obligatoire, CI requise) : les PR sont pour l'instant mergées sans review.
- Remplir la section **Contributions** du README à partir de l'historique Git avant le rendu.

---

## Répartition proposée (sans rôle attitré)

Cinq chantiers indépendants, menés en parallèle grâce au contrat d'API et aux métriques déjà en place :

1. Scripts d'attaque et vérification de l'IP réelle sur le réseau du groupe
2. Détecteur ML
3. Moteur de remédiation et playbooks
4. Scénario de bout en bout, puis Vault et dashboard sécurité
5. Gouvernance et dossier (à démarrer dès maintenant, ne bloque personne)

---

## Limites connues et points de vigilance

- **HTTPS** hors périmètre du laboratoire (pas de domaine ni de certificat) : documenté comme limite.
- **Droits sur les comptes** : tout utilisateur connecté peut débiter n'importe quel compte de démonstration.
- **IP réelle masquée par Docker Desktop** : le WAF voit la passerelle Docker pour tout le trafic externe. Un ban coupe donc tout l'externe pendant sa durée ; le canary interne n'est pas touché.
- **WAF sur `192.168.137.1`** : si le point d'accès n'est pas actif avant Docker, le WAF reste à l'état `Created`. En développement : `WAF_BIND_IP=127.0.0.1`.
- **Règle CRS 920350 exclue** (Host en adresse IP) : justifié dans `security/waf/crs-exclusions.conf`.
- **npm 10** (fourni avec Node 22) plante sur les dépendances de vitest 5 : npm 11.21.0 est épinglé dans les Dockerfile et la CI.
- **PowerShell 5.1** abîme les guillemets imbriqués passés à un programme externe : préférer des scripts versionnés (exemple : `tests/e2e/transaction_curl.sh`).
