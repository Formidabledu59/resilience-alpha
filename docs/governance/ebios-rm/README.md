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
4. Le moteur bannit la source au WAF, vérifie le canari, exécute une transaction de contrôle.

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

| Mesure | Scénarios couverts | État |
|---|---|---|
| WAF ModSecurity + OWASP CRS, rate-limit | SO1, SO2, SO3 | Fait |
| Détection d'anomalies (Isolation Forest) | SO1 | Fait |
| Remédiation autonome (ban IP, restart, vérification canari) | SO1, SO3 | Fait |
| Règles SOC (Loki) + alertes (Alertmanager) | SO1, SO2, SO3 | Fait |
| Vault (secrets chiffrés, lecture seule par service) | ER3, SO4 | Fait |
| Segmentation réseau, moindre privilège, non-root, read-only | SO4 | Fait |
| Journal d'audit chaîné SHA-256 | ER5 | Fait |
| Preuve de reprise par transaction métier (canari) | ER1, ER4 | Fait |

### Matrice du risque résiduel

Vraisemblance et gravité après mesures (échelle 1 à 4).

| Scénario | Gravité | Vraisemblance résiduelle | Risque résiduel |
|---|---|---|---|
| SO1 DoS applicatif | 4 | 2 (absorbé par WAF + reprise auto) | Moyen |
| SO2 Injection web | 4 | 1 (bloqué par le CRS) | Faible |
| SO3 Force brute | 3 | 1 (rate-limit + SOC) | Faible |
| SO4 Compromission conteneur | 4 | 2 (durcissement, pas éliminé) | Moyen |

### Risques résiduels assumés (contexte POC)

- **Mono-hôte, pas de haute disponibilité réelle** : une panne du PC Hôte arrête tout.
- **IP réelle masquée par Docker Desktop** : un ban coupe tout le trafic externe (le canari
  interne prouve quand même la reprise).
- **Modèle ML entraîné sur un trafic simulé** : à ré-entraîner sur des données réelles.
- **Pas de TLS** (laboratoire sans domaine ni certificat).

Ces risques sont acceptés dans le cadre du démonstrateur et documentés comme axes d'amélioration
pour une version industrielle (voir le dossier d'ingénierie et [`../pca-pra/`](../pca-pra/)).
