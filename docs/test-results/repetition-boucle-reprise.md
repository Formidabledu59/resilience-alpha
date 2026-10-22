# Répétition de la boucle de reprise (Docker, PC Hôte)

> Essai du 21 octobre 2026, PC Hôte, stack complète en développement (`WAF_BIND_IP=127.0.0.1`).
> Profiles `app`, `security`, `remediation` + `ml-detector`. 17 conteneurs `healthy`.

## Objectif

Vérifier, en conteneurs réels, que la plateforme détecte une panne et se rétablit **sans
intervention humaine**, la reprise étant prouvée par une transaction métier réussie.

## Déroulé

Panne provoquée : arrêt du conteneur `payment-api` (`docker stop`), qui coupe la chaîne de
paiement. Observé sur le dashboard, Prometheus et le journal des incidents.

| t (s) | `canary_up` | score ML | payment-api | incident |
|---|---|---|---|---|
| 0 | 1 | 0,05 | arrêté | - |
| 11 | 0 | 0,34 | arrêté | - |
| 33 | 0 | 0,56 | arrêté | - |
| 43 | 0 | 0,67 | arrêté | - |
| 54 | 0→1 | 0,70 | **redémarré** | inc-002 VERIFYING |
| ~67 | 1 | ↓ | running | inc-002 CLOSED |

Étapes de l'incident `inc-2026-10-21-002` (journal) :

```
08:17:12  Alerte reçue : TargetDown (bearer valide)  :: Cible payment-api injoignable
08:17:12  Collecte des preuves (Prometheus, Loki)    :: canari au plus bas 25,0 %
08:17:14  Playbook restart_api.yml                   :: payment-api redémarré
08:17:14  Attente du retour nominal du canari        :: canary_up = 1 et succès >= 95 %
08:18:19  Vérification canary_up                     :: 1, taux de succès 100,0 %
08:18:19  Transaction de contrôle (POST /probe)      :: COMPLETED, transaction n°2491
```

Issue : **« Reprise prouvée par une transaction de contrôle réussie »**. Durée totale ~67 s.

## Vérifications complémentaires

- Transaction métier via le WAF après reprise : `{"id":2497,"status":"COMPLETED"}`.
- Score ML revenu à 0,05 (nominal).
- Journal d'audit : `journal/verify` → `ok:true`, 24 entrées, chaîne SHA-256 intacte.
- Playbook Ansible exécuté via `socket-proxy-rw` (restart du conteneur), `returncode 0`.
- Un **premier** incident (`inc-001`) s'était déjà ouvert et clôturé seul au démarrage
  (remediation-engine brièvement injoignable) : la boucle a donc tourné deux fois.

## Ce que l'essai prouve

- La boucle complète fonctionne en conteneurs : alerte → preuves → playbook Ansible →
  vérification canari → transaction de contrôle → clôture. Le journal est chaîné et vérifiable.
- Le redémarrage d'un service par Ansible passe bien par `socket-proxy-rw` (droits minimaux),
  sans accès direct au socket Docker.

## Points relevés

> **Traités le 22/10** ([répétition générale](repetition-generale.md)) : le chemin ML a été démontré sur un DoS réel (6 essais sur 6), le modèle est entraîné sur du trafic réel, le DoS est calibré. Reste à rejouer l'attaque depuis le PC Attaquant.

1. **TargetDown déclenche avant le détecteur ML** quand un service est *arrêté* : l'alerte
   Prometheus (30 s + `group_wait` 10 s) part avant que le ML ait 3 relevés au-dessus du seuil.
   Le ML n'a donc pas envoyé d'alerte ici (`ml_alerts_sent_total` vide). C'est attendu : le
   **chemin ML se démontre avec le DoS** (service *dégradé* mais toujours UP, donc pas de
   TargetDown). À montrer une fois le DoS calibré (voir `calibrage-attaque-dos.md`).
2. **Modèle ML de repli synthétique** (`ml_model_fallback = 1`) : il a bien vu la montée
   (score 0,05 → 0,70), mais pour la démo « détection ML », collecter de vraies données
   nominales et entraîner le modèle (`ml/training/collect.py` puis `train.py`).
3. **Images frontend et dashboard** : `docker compose build` seul n'avait pas repris les
   modifications (ancienne image servie). Reconstruire avec `docker compose build --no-cache
   frontend dashboard` après un `git pull`, ou `docker compose up -d --build`.

## Reste à faire (mis à jour le 22/10)

- ~~Calibrer le DoS pour déclencher le chemin ML~~ : fait le 22/10 ([calibrage](calibrage-attaque-dos.md)).
- ~~Entraîner le modèle ML sur des données collectées~~ : fait le 22/10 (121 relevés réels).
- Rejouer l'attaque **depuis le PC Attaquant** (les essais du 22/10 partaient du PC Hôte).
