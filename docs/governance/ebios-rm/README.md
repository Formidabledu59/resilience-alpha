# Analyse de risques EBIOS Risk Manager

> Analyse appliquée au démonstrateur Resilience Alpha (groupe 16). Méthode ANSSI EBIOS RM.
> Cadre : laboratoire, données exclusivement fictives. L'analyse est volontairement resserrée
> sur le périmètre du POC ; les valeurs de gravité et de vraisemblance sont celles du contexte
> de démonstration, pas d'une production réelle.

EBIOS RM se déroule en cinq ateliers : cadrage, sources de risque, scénarios stratégiques,
scénarios opérationnels, traitement du risque.

---

## Atelier 1 - Cadrage et socle de sécurité

### Mission et valeurs métier

| Valeur métier | Description | Besoin de sécurité (D / I / C) |
|---|---|---|
| Exécution des paiements | Traiter une transaction fictive de bout en bout | **Disponibilité** forte, **Intégrité** forte |
| Intégrité des comptes | Solde juste, débit et crédit atomiques | Intégrité forte |
| Confiance dans la reprise | Prouver le retour à un état utilisable après incident | Disponibilité forte |
| Secrets de la plateforme | Clés JWT, mot de passe de la base | Confidentialité forte |
| Traçabilité des incidents | Journal d'audit des attaques et des remédiations | Intégrité forte, Disponibilité moyenne |

### Biens supports

| Bien support | Valeur(s) métier portée(s) |
|---|---|
| `payment-api`, `auth-service`, `postgres` | Exécution des paiements, intégrité des comptes |
| `waf` (Nginx + ModSecurity CRS) | Point d'entrée unique, filtrage |
| `vault` | Secrets de la plateforme |
| `canary` | Preuve de disponibilité métier |
| `ml-detector`, `remediation-engine`, playbooks Ansible | Détection et reprise autonome |
| Journal d'incidents (chaîné SHA-256) | Traçabilité |
| PC Hôte (Docker Desktop, WSL2) et réseau `RESILIENCE-G16` | Tous |

### Événements redoutés

| Id | Événement redouté | Valeur impactée | Gravité |
|---|---|---|---|
| ER1 | Indisponibilité du service de paiement | Exécution des paiements | **4 - Critique** |
| ER2 | Altération d'une transaction ou d'un solde | Intégrité des comptes | 4 - Critique |
| ER3 | Divulgation des secrets (JWT, base) | Secrets | 3 - Grave |
| ER4 | Reprise non prouvée ou masquée (fausse confiance) | Confiance dans la reprise | 3 - Grave |
| ER5 | Altération du journal d'incidents | Traçabilité | 2 - Significatif |

### Socle de sécurité (mesures déjà en place)

Hygiène ANSSI appliquée au POC : conteneurs non-root, systèmes de fichiers en lecture seule,
`cap_drop: [ALL]`, réseaux Docker internes segmentés (7 réseaux), aucun secret en clair (Vault +
`.env` ignoré par Git), un seul port publié (le WAF), interfaces d'administration liées à
`127.0.0.1`, accès Docker de la remédiation filtré par un proxy à droits minimaux. Écarts connus :
pas de TLS (laboratoire), IP réelle masquée par Docker Desktop (voir `security/waf/README.md`).

---

## Atelier 2 - Sources de risque et objectifs visés

| Source de risque (SR) | Objectif visé (OV) | Pertinence |
|---|---|---|
| Cybercriminel opportuniste | Rendre le service indisponible (extorsion, nuisance) | **Forte** - scénario principal de la démo |
| Hacktiviste | Défigurer ou perturber une plateforme de paiement | Moyenne |
| Script kiddie / scanner automatisé | Exploiter une vulnérabilité connue (injection, Log4Shell) | Forte |
| Attaquant interne au réseau du groupe | Accès latéral, vol de secrets | Moyenne (cadre labo) |

Couples SR/OV retenus pour la suite : **cybercriminel → indisponibilité** et
**scanner/attaquant applicatif → exploitation d'une faille**.

---

## Atelier 3 - Scénarios stratégiques

Chemins d'attaque de haut niveau, du point d'entrée vers les événements redoutés.

| Id | Scénario stratégique | Chemin | ER visé |
|---|---|---|---|
| SS1 | Déni de service applicatif depuis le réseau du groupe | PC Attaquant → WAF → chaîne de paiement | ER1 |
| SS2 | Exploitation d'une vulnérabilité web | PC Attaquant → WAF → payment-api / auth-service | ER2, ER3 |
| SS3 | Force brute sur l'authentification | PC Attaquant → WAF → auth-service | ER3 |
| SS4 | Compromission d'un conteneur exposé | Faille applicative → exécution dans un conteneur → rebond | ER2, ER3 |

> La surface d'exposition est réduite par conception : seul le WAF est joignable depuis le
> réseau. Les scénarios passent donc tous par lui, ce qui concentre la défense.

---

## Atelier 4 - Scénarios opérationnels

Déclinaison technique des scénarios stratégiques (séquence réelle d'une attaque).

### SO1 - Déni de service applicatif (dérivé de SS1, démonstration principale)

1. L'attaquant lance `attack/dos/flood.py` (flood authentifié) contre `http://192.168.137.1`.
2. Le trafic sature le rate-limit du WAF puis du frontal ; la latence monte, le canari échoue.
3. `ml-detector` voit l'anomalie (score au-dessus du seuil) et alerte `remediation-engine`.
4. Le moteur bannit la source au WAF, relance payment-api, vérifie le canari, exécute une
   transaction de contrôle.

> **Démontré le 22/10** ([répétition générale](../../test-results/repetition-generale.md)), attaque
> lancée depuis le PC Hôte (à rejouer depuis le PC Attaquant) : 6 essais réussis sur 6, détection par le ML, ban de l'attaquant, relance, transaction de contrôle
> `COMPLETED`. Condition : limites de débit relâchées pour la démonstration. Aux réglages par
> défaut, le WAF et le frontal absorbent le flood (le canari reste à 1, score ML ≤ 0,43) et c'est
> la règle SOC qui bannit l'attaquant en ~5 s ([calibrage](../../test-results/calibrage-attaque-dos.md)).

### SO2 - Injection SQL / XSS (dérivé de SS2)

1. L'attaquant envoie des charges d'injection (`attack/sqli/inject.py`).
2. ModSecurity (OWASP CRS, règles 942xxx / 941xxx) bloque en `403` avant d'atteindre l'API.
3. Les blocages alimentent le SOC (Loki + règles) et le bilan d'incident.

### SO3 - Force brute sur `auth-service` (dérivé de SS3)

1. Tentatives répétées de connexion.
2. Rate-limit `/api/auth/token` (10/min) + règle SOC `EchecsConnexionRepetes` → alerte.

### SO4 - Compromission d'un conteneur (dérivé de SS4)

1. Exploitation d'une faille applicative hypothétique.
2. Limites : non-root, `read_only`, `cap_drop`, réseaux internes, pas de `docker.sock` dans les
   conteneurs métier (seuls les deux socket-proxy le montent, en lecture seule). Le rebond est
   contraint par la segmentation réseau.

---

## Atelier 5 - Traitement du risque

### Mesures de sécurité et couverture

| Mesure | Scénarios couverts | État | Preuve |
|---|---|---|---|
| WAF ModSecurity + OWASP CRS, rate-limit | SO1, SO2, SO3 | Fait, vérifié | `attack/sqli/inject.py` (403), `security/waf/README.md` |
| Détection d'anomalies (Isolation Forest) | SO1 | Fait, **démontré sur DoS** (22/10, 6/6) | `repetition-generale.md`, `ml/detector/tests/` |
| Remédiation autonome (ban IP, restart, vérification canari) | SO1, SO3 | Démontrée sur panne de service (21/10) et sur DoS (22/10) ; force brute **non testée** | `repetition-generale.md`, `repetition-boucle-reprise.md` |
| Règles SOC (Loki) + alertes (Alertmanager) | SO1, SO2, SO3 | Fait, vérifié (inactive → pending → firing) | `security/soc-rules/README.md` |
| Vault (secrets chiffrés, lecture seule par service) | ER3, SO4 | Fait, vérifié | `security/vault/README.md` |
| Segmentation réseau, moindre privilège, non-root, read-only | SO4 | Fait | `docker-compose.yml`, `security/hardening.md` |
| Journal d'audit chaîné SHA-256 | ER5 | Fait, vérifié (`/journal/verify`) | `services/remediation-engine/tests/` |
| Preuve de reprise par transaction métier (canari) | ER1, ER4 | Fait, démontré | `repetition-boucle-reprise.md` |

### Matrice du risque résiduel

Vraisemblance et gravité après mesures (échelle 1 à 4).

| Scénario | Gravité | Vraisemblance résiduelle | Risque résiduel |
|---|---|---|---|
| SO1 DoS applicatif | 4 | 2 (absorbé par le WAF et banni par le SOC aux réglages par défaut ; détecté par le ML et remédié en 37 à 75 s quand l'attaque passe) | Moyen |
| SO2 Injection web | 4 | 1 (bloqué par le CRS) | Faible |
| SO3 Force brute | 3 | 1 (rate-limit + SOC) | Faible |
| SO4 Compromission conteneur | 4 | 2 (durcissement, pas éliminé) | Moyen |

### Risques résiduels assumés (contexte POC)

- **Mono-hôte, pas de haute disponibilité réelle** : une panne du PC Hôte arrête tout.
- **IP réelle masquée par Docker Desktop** : un ban coupe tout le trafic externe (le canari
  interne prouve quand même la reprise).
- **Modèle ML entraîné sur un court échantillon de trafic réel** (20 minutes) : à ré-entraîner sur un historique long.
- **Pas de TLS** (laboratoire sans domaine ni certificat).

Ces risques sont acceptés dans le cadre du démonstrateur. Arbitrages et recommandations pour une
version industrielle : [`../recommandations.md`](../recommandations.md) ; continuité : [`../pca-pra/`](../pca-pra/).
