# Runbooks d'incident

> Procédures d'intervention pour le démonstrateur Resilience Alpha (groupe 16). Cadre laboratoire.
> La plupart des incidents sont traités **automatiquement** par la boucle de reprise ; ces
> runbooks servent à comprendre la réponse, à vérifier à la main, et à reprendre la main si un
> incident passe en `FAILED`.

## Outils de l'opérateur

| Outil | Adresse | Usage |
|---|---|---|
| Dashboard de supervision | http://127.0.0.1:5173 | Phase, chiffres clés, journal des incidents, transaction de contrôle |
| Assistant opérateur (RAG) | http://127.0.0.1:8501 | Retrouver une procédure (lecture seule) |
| Grafana | http://127.0.0.1:3000 | Dashboards observabilité et sécurité |
| Prometheus | http://127.0.0.1:9090 | `canary_up`, `ml_anomaly_score`, cibles |

Réflexe commun : **la reprise n'est acquise que si une transaction de contrôle réussit**
(bouton du dashboard ou `POST /probe` du canari), avec `canary_up = 1`.

---

## RB1 - Déni de service applicatif

**Symptômes** : phase « Pendant » sur le dashboard, `canary_up` à 0 ou taux de succès en baisse,
score ML au-dessus du seuil, pic de `429` au WAF.

**Réponse automatique** : `ml-detector` alerte `remediation-engine` (incident « anomalie »), qui
bannit la source au WAF (`ban_ip.yml`, seulement si une IP dépasse 100 refus 403/429) puis
relance payment-api (`restart_api.yml`). Si c'est le SOC qui alerte (`WafRateLimitSature`),
seul le ban est appliqué. Le moteur attend ensuite 3 relevés `canary_up = 1`, puis exécute une
transaction de contrôle. Ban temporaire (5 min), levé automatiquement.

**Vérification manuelle** :
1. Journal de l'incident (dashboard) : étapes ban → vérification → transaction de contrôle.
2. `canary_up = 1` dans Prometheus, phase revenue à « Après ».

**Si `FAILED`** : vérifier que le WAF a bien rechargé (log `waf`), au besoin relancer une
transaction de contrôle ; si l'attaque persiste, prolonger le ban manuellement (fichier dans le
volume `waf-banlist`, puis `HUP` au WAF via socket-proxy-rw).

---

## RB2 - Indisponibilité d'un service

**Symptômes** : `TargetDown` dans Prometheus, service `DOWN`, canari en échec.

**Réponse automatique** : `remediation-engine` exécute `restart_api.yml` (redémarrage via
socket-proxy-rw), attend `canary_up = 1`, puis transaction de contrôle.

**Vérification manuelle** :
1. `docker compose ps -a` : le service est-il `healthy` ?
2. Transaction de contrôle réussie, incident `CLOSED`.

**Si `FAILED`** : consulter les logs du service (`docker logs resilience-alpha-<service>-1`),
corriger la cause (dépendance, configuration), relancer, puis valider par une transaction.

---

## RB3 - Attaque applicative (injection SQL, XSS, scanner)

**Symptômes** : pic de `403` au WAF, règle SOC `WafBlocagesModSecurity` ou `WafScannerDetecte`.

**Réponse** : ModSecurity (OWASP CRS) bloque en amont ; le service n'est pas dégradé. Aucune
action corrective n'est nécessaire, l'incident sert à qualifier et tracer.

**Vérification manuelle** :
1. Dashboard Grafana « Frontal et sécurité » : règles déclenchées, clients bloqués.
2. Confirmer que `canary_up` est resté à 1 (aucun impact métier).

---

## RB4 - Force brute sur l'authentification

**Symptômes** : rafale de `401` sur `/auth/token`, règle SOC `EchecsConnexionRepetes`.

**Réponse automatique** : alerte → ban de la source. Le rate-limit `/api/auth/token` (10/min)
limite déjà la cadence.

**Vérification manuelle** : journal de l'incident, puis `canary_up = 1`.

---

## RB5 - Échec de remédiation (`FAILED`)

**Symptômes** : un incident reste en `FAILED` dans le journal ; la transaction de contrôle n'a
pas abouti dans le délai.

**Procédure** :
1. Ouvrir le rapport de l'incident (dashboard, « Télécharger le rapport »).
2. Lire la chronologie : quelle étape a échoué (playbook, vérification, transaction) ?
3. Appliquer le runbook du type d'incident (RB1 à RB4).
4. Rétablir le service, puis **prouver** par une transaction de contrôle.
5. Vérifier l'intégrité du journal (`/journal/verify` : `ok: true`).

---

## RB6 - Secret potentiellement exposé

**Symptômes** : secret commité par erreur (la CI `gitleaks` échoue), ou doute sur une clé.

**Procédure** :
1. Ne pas se contenter de supprimer le fichier : un secret commité reste dans l'historique Git.
2. **Révoquer et renouveler** le secret concerné (régénérer la valeur dans `.env`, redémarrer les
   services qui le lisent ; pour les secrets Vault, mettre à jour le chemin KV).
3. Vérifier qu'aucune donnée réelle n'était concernée (le projet n'utilise que des données
   fictives).
4. Tracer l'incident et la rotation effectuée.

---

## RB7 - Compromission suspectée d'un conteneur

**Symptômes** : comportement anormal d'un conteneur, trafic inattendu, alerte non expliquée par
une attaque connue.

**Procédure (confinement d'abord)** :
1. Isoler : arrêter le conteneur suspect (`docker stop`) ; la segmentation réseau limite déjà le
   rebond (réseaux internes, pas de `docker.sock` dans les conteneurs métier).
2. Conserver les logs (Loki) et le journal d'incidents pour analyse.
3. Reconstruire le conteneur à partir de l'image saine (`docker compose up -d --build <service>`).
4. Vérifier Vault (aucun accès anormal), renouveler les secrets par précaution (RB6).
5. Prouver la reprise par une transaction de contrôle.

---

## Remise à zéro complète (dernier recours)

```powershell
docker compose --profile '*' down -v   # arrêt et suppression des volumes (base, métriques, logs)
```

Puis redémarrer selon [`../governance/pca-pra/`](../governance/pca-pra/) section 5.3. À n'utiliser
qu'en démonstration : efface toutes les données (fictives) et l'historique des incidents.
