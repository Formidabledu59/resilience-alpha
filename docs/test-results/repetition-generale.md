# Répétition générale de la boucle de reprise

Essais chronométrés produits par `tests/e2e/resilience_scenario.py --runs 3 --report ...`, sur le PC Hôte, point d'accès `RESILIENCE-G16` actif, attaque envoyée sur le WAF (`192.168.137.1`), stack complète, modèle ML entraîné sur 20 minutes de trafic nominal réel (121 relevés).

> L'attaque partait du **PC Hôte lui-même** (vers sa propre adresse sur le point d'accès). Le sujet exige un PC Attaquant distinct : à rejouer depuis ce poste avant le jury (même chemin jusqu'au WAF, latence WiFi en plus).

Durées lues dans le journal d'incidents : **détection** = lancement de l'attaque → ouverture de l'incident ; **remédiation + vérification** = ouverture → clôture (après la transaction de contrôle).

Réglages (proposés pour la démonstration, voir [`calibrage-attaque-dos.md`](calibrage-attaque-dos.md)) : limites de débit du WAF et du frontal relâchées à 2000 r/s, flood authentifié, concurrence 200.

## Synthèse

**La boucle complète est démontrée en conditions réelles** : attaque envoyée sur le WAF du point d'accès, **détection par le ML** (Isolation Forest entraîné sur du trafic réel), ban de l'attaquant et relance de payment-api par Ansible, vérification par le canari, **transaction de contrôle `COMPLETED`**, incident clos, transaction métier finale réussie. **6 essais réussis sur 6** dans les deux dernières séries, tous détectés par le ML, sans aucune intervention humaine.

| Série | Résultat | Ce que la série a révélé | Correction |
|---|---|---|---|
| 09:09 | 0/3 | Point d'accès éteint par Windows toutes les ~5 min sans client : WAF injoignable (essais 1 et 2). Essai 3 : vérification validée sur des métriques **antérieures au redémarrage**, transaction de contrôle en HTTP 502 → `FAILED` | Moteur : 3 relevés `canary_up = 1` toujours exigés après l'action, transaction de contrôle réessayée (3 fois). Scénario : réessai sur coupure réseau |
| 09:17 | 2/3 | Le ML **réalertait chaque minute** après un incident clos (moyennes sur 1 min qui gardent la trace de l'attaque) : remédiations inutiles en boucle | Détecteur : réarmement, pas de nouvelle alerte avant 3 relevés sous le seuil |
| 09:25 | **3/3** | Avec les limites relâchées, aucun refus WAF : **l'attaquant n'était pas banni**, seul le redémarrage soulageait le service | Moteur : ban aussi sur le **volume** de requêtes (journaux du WAF dans Loki) |
| 09:41 | **3/3** | Attaquant banni dès que le volume dépasse le seuil ; un essai sous le seuil de 3 000 requêtes (1 883 mesurées) | Seuil abaissé à 1 000 requêtes (canary : ~60) |

**Durées** (6 essais réussis) : détection 20 à 51 s (elle dépend du moment où payment-api cède sous la charge), remédiation + vérification 15 à 46 s, total **37 à 75 s**. **3 essais sur 6 tiennent dans les 60 s du Clip Chrono.** Les deux essais les plus lents ont subi une coupure du point d'accès en plein incident (WAF recréé, canari en échec pendant ~15 s), ce qui n'arrivera pas avec le PC Attaquant connecté au point d'accès.

**Pour le Clip Chrono** : désactiver l'économie d'énergie du point d'accès, garder le PC Attaquant connecté, et filmer plusieurs prises si besoin (chacune en plan continu, sans coupe). Leviers si la boucle reste au-delà de 60 s : `ML_ALERT_CONSECUTIVE=2` (détection ~5 s plus tôt).

## Essais du 22/10/2026 09:09 UTC

Réglages : attaque 90 s, concurrence 200, flood authentifié, cible http://192.168.137.1.

| Essai | Résultat | Détecté par | Détection | Remédiation + vérification | Total | Clip (≤ 60 s) | Incident |
|---|---|---|---|---|---|---|---|
| 1 | ÉCHEC | - | - | - | - | non | - |
| 2 | ÉCHEC | - | - | - | - | non | - |
| 3 | ÉCHEC | ML (Isolation Forest) | 38 s | 4 s | 42 s | oui | inc-2026-10-22-005 |

**0/3 essais réussis.**

- Essai 1 : erreur réseau : timed out. La stack complète est-elle démarrée (profiles app, ia, remediation) ?
- Essai 2 : erreur réseau : [WinError 10013] Une tentative d’accès à un socket de manière interdite par ses autorisations d’accès a été tentée. La stack complète est-elle démarrée (profiles app, ia, remediation) ?
- Essai 3 : incident inc-2026-10-22-005 en échec (FAILED) : reprise non prouvée

## Essais du 22/10/2026 09:17 UTC

Réglages : attaque 90 s, concurrence 200, flood authentifié, cible http://192.168.137.1.

| Essai | Résultat | Détecté par | Détection | Remédiation + vérification | Total | Clip (≤ 60 s) | Incident |
|---|---|---|---|---|---|---|---|
| 1 | OK | ML (Isolation Forest) | 37 s | 16 s | 53 s | oui | inc-2026-10-22-007 |
| 2 | OK | ML (Isolation Forest) | 37 s | 27 s | 64 s | non | inc-2026-10-22-009 |
| 3 | ÉCHEC | - | - | - | - | non | - |

**2/3 essais réussis.**

- Essai 3 : plateforme pas revenue au nominal entre deux essais

## Essais du 22/10/2026 09:25 UTC

Réglages : attaque 90 s, concurrence 200, flood authentifié, cible http://192.168.137.1.

| Essai | Résultat | Détecté par | Détection | Remédiation + vérification | Total | Clip (≤ 60 s) | Incident |
|---|---|---|---|---|---|---|---|
| 1 | OK | ML (Isolation Forest) | 20 s | 46 s | 66 s | non | inc-2026-10-22-012 |
| 2 | OK | ML (Isolation Forest) | 22 s | 15 s | 37 s | oui | inc-2026-10-22-013 |
| 3 | OK | ML (Isolation Forest) | 51 s | 24 s | 75 s | non | inc-2026-10-22-014 |

**3/3 essais réussis.**

## Essais du 22/10/2026 09:41 UTC

Réglages : attaque 90 s, concurrence 200, flood authentifié, cible http://192.168.137.1.

| Essai | Résultat | Détecté par | Détection | Remédiation + vérification | Total | Clip (≤ 60 s) | Incident |
|---|---|---|---|---|---|---|---|
| 1 | OK | ML (Isolation Forest) | 40 s | 19 s | 59 s | oui | inc-2026-10-22-015 |
| 2 | OK | ML (Isolation Forest) | 38 s | 16 s | 54 s | oui | inc-2026-10-22-017 |
| 3 | OK | ML (Isolation Forest) | 35 s | 34 s | 69 s | non | inc-2026-10-22-018 |

**3/3 essais réussis.**
