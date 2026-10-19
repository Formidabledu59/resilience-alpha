# État des lieux du projet

> Mis à jour le 19 octobre 2026, après la PR #6. À tenir à jour à chaque PR importante.
> Échéances : gel du code **jeudi 17h**, dépôt des livrables **jeudi 23h59**.

## En résumé

**Avancement estimé : environ 30 %.** La fondation est en place et vérifiée : infrastructure, observabilité, chaîne de paiement, frontal et dashboard.
Reste le **coeur de la démonstration** : WAF, attaque, détection ML et remédiation automatique, puis la gouvernance et les livrables.

| Bloc | Poids estimé | Avancement | Contribution |
|---|---|---|---|
| Infrastructure et observabilité | 15 % | 90 % | 13,5 % |
| Services métier, frontal, dashboard | 15 % | 90 % | 13,5 % |
| Cybersécurité (WAF, Vault, SOC, attaques) | 15 % | 10 % | 1,5 % |
| IA (détection, assistant RAG) | 15 % | 0 % | 0 % |
| Remédiation et boucle de reprise | 15 % | 10 % | 1,5 % |
| Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | 10 % | 5 % | 0,5 % |
| Livrables (dossier, présentation, clip) | 15 % | 0 % | 0 % |
| **Total** | | | **environ 30 %** |

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
| Grafana | Dashboards « Vue globale » et « Frontal et sécurité » | #3, #6 |
| CI | 5 jobs verts : gitleaks, yamllint, pytest, front (frontend), front (dashboard) | #1, #6 |
| Documentation | README, `infra/README.md`, `docs/architecture/contracts.md`, README de chaque service développé, procédure d'utilisation | toutes |

Vérifié au runtime : 12 conteneurs `healthy`, transaction `COMPLETED` depuis le navigateur et en ligne de commande, `canary_up = 1`, logs de tous les services dans Loki, aucune adresse IP dans les journaux du frontal.

---

## Ce qu'il reste à faire

### Priorité 1 : la boucle de démonstration (attaque, détection, remédiation, preuve)

| Tâche | Détail | Pilier |
|---|---|---|
| WAF | `security/waf/nginx.conf` : proxy vers frontend, auth-service et payment-api, `/healthz`, rate-limit, inclusion de la liste de ban (volume `waf-banlist`), logs ModSecurity en JSON. Puis basculer le canary sur le WAF (`AUTH_URL` et `PAYMENT_URL` = `http://waf:8080`) | cyber |
| Attaque DoS | `attack/dos/` : cible en paramètre, refus de toute cible hors `192.168.137.0/24` | cyber |
| Détecteur ML | Collecte des métriques sous trafic nominal, entraînement Isolation Forest (`ml/training/`), service `ml/detector` (score toutes les 5 s, `ml_anomaly_score` et `ml_anomaly_threshold` dans `/metrics`, webhook signé HMAC) | ia |
| Moteur de remédiation | Webhooks HMAC (ml-detector) et bearer (Alertmanager), liste blanche de playbooks, `GET /incidents` (contrat dans `contracts.md`), journalisation dans Loki | infra, dev |
| Playbooks Ansible | `ban_ip.yml` (écrit dans `waf-banlist` puis recharge le WAF via socket-proxy-rw), `restart_api.yml`, `verify.yml` (attend `canary_up == 1` puis `POST /probe`) | infra |
| Scénario de bout en bout | `tests/e2e/resilience_scenario.py`, puis répétition réelle depuis le PC Attaquant | dev, infra |

### Priorité 2 : compléter le visible et la sécurité

| Tâche | Détail | Pilier |
|---|---|---|
| Dashboard sécurité | Blocages ModSecurity dans Grafana, règles SOC (`security/soc-rules/`) | cyber |
| Scénario d'injection | `attack/sqli/` : tentative bloquée par le WAF, tracée dans le SOC | cyber |
| Vault | `config.hcl`, `init.sh` (sans afficher de secret), lecture de `JWT_SECRET` et des identifiants de base | cyber |
| Durcissement documenté | `security/hardening.md` | cyber |
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

1. WAF et scripts d'attaque
2. Détecteur ML
3. Moteur de remédiation et playbooks
4. Scénario de bout en bout, puis Vault et dashboard sécurité
5. Gouvernance et dossier (à démarrer dès maintenant, ne bloque personne)

---

## Limites connues et points de vigilance

- **HTTPS** hors périmètre du laboratoire (pas de domaine ni de certificat) : documenté comme limite.
- **Droits sur les comptes** : tout utilisateur connecté peut débiter n'importe quel compte de démonstration.
- **Rate-limit du frontal** : derrière le WAF, il faudra utiliser `X-Forwarded-For`, sinon tous les clients partagent la même limite.
- **npm 10** (fourni avec Node 22) plante sur les dépendances de vitest 5 : npm 11.21.0 est épinglé dans les Dockerfile et la CI.
- **PowerShell 5.1** abîme les guillemets imbriqués passés à un programme externe : préférer des scripts versionnés (exemple : `tests/e2e/transaction_curl.sh`).
