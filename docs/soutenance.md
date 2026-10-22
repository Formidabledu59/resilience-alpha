# Soutenance — déroulé et diaporama

> Jury local, vendredi 23/10 : **10 minutes** = **5 minutes** de présentation et de démonstration, puis **5 minutes** de questions. Le temps est noté (axe 4 : « 5 min respectées »). Démonstration **sur nos machines**, sans toucher au PC Hôte pendant la reprise.

## Ce que le jury note (rappel)

| Axe | Points | Ce qui doit se voir |
|---|---|---|
| 1. Démonstration et remédiation autonome | 5 | Attaque **depuis le PC Attaquant**, détection, reprise **sans intervention**, **nouvelle transaction réussie**. Une intervention humaine pendant le live = **0/5** |
| 2. Expertise et cohérence des 5 piliers | 4 | Piliers réellement reliés, **ML branché sur la remédiation**, accès du moteur de remédiation maîtrisés |
| 3. Clip Chrono et dashboard | 4 | 60 s en continu, état visible avant / pendant / après |
| 4. Gouvernance, NIS2/DORA, pitch | 4 | EBIOS et PCA/PRA reliés à **notre** architecture, recommandations argumentées, 5 min tenues |
| 5. Dossier et réponses | 3 | Contribution de chacun visible, maîtrise du code (y compris généré par IA) |

## L'idée directrice : lancer l'attaque tôt

La boucle prend **40 à 75 s** entre l'attaque et la reprise prouvée ([répétition générale](test-results/repetition-generale.md)). On lance donc l'attaque vers **1:00** et on présente l'architecture pendant qu'elle se déroule : le jury voit la reprise se faire seule, sans que personne ne touche au PC Hôte.

## Déroulé minute par minute (5:00)

| Temps | Diapo | Ce qu'on dit / fait | Écran montré |
|---|---|---|---|
| 0:00 – 0:30 | 1. Titre et équipe | Chaque membre se présente en une phrase (son pilier principal) | Diaporama |
| 0:30 – 1:00 | 2. Le problème | Un paiement qui ne passe plus : ce que coûte un arrêt (1 h ≈ 72 000 paiements bloqués, hypothèses fictives), ce que nous protégeons : **la capacité à payer**, prouvée par une vraie transaction | Diaporama |
| 1:00 – 1:10 | 3. Démonstration (annonce) | « Avant » : dashboard nominal, canari 100 %. **Le PC Attaquant lance l'attaque** | Dashboard + PC Attaquant |
| 1:10 – 2:10 | 4. Architecture et boucle | Pendant l'attaque : les 5 piliers sur un schéma ; la boucle collecte → **détection ML** → décision → **Ansible** (ban + relance) → **transaction de contrôle**. Regarder le dashboard passer **Pendant → Remédiation** | Diaporama, puis dashboard |
| 2:10 – 2:40 | (démo) | « Après » : **Reprise confirmée**, journal de l'incident (étapes horodatées), puis **une nouvelle transaction sur le frontal** devant le jury | Dashboard, journal, frontal |
| 2:40 – 3:20 | 5. Détection par ML | Isolation Forest sur 6 indicateurs Prometheus, entraîné sur **notre trafic réel** ; ce qu'il détecte et ce qu'il ne détecte pas ; réarmement anti-boucle | Diaporama |
| 3:20 – 3:50 | 6. Sécurité | WAF + SOC (Loki), Vault, segmentation ; **moteur de remédiation sans accès direct à Docker** (proxy limité, liste blanche de playbooks) | Diaporama |
| 3:50 – 4:30 | 7. Gouvernance | EBIOS RM (scénario retenu), PCA/PRA (**RTO < 3 min, mesuré 37 à 75 s**), NIS2/DORA (DORA s'applique, ce qu'un POC ne démontre pas), **disponibilité ≠ compromission** | Diaporama |
| 4:30 – 5:00 | 8. Limites et recommandations | Mono-hôte, IP masquée par Docker Desktop, limites de débit relâchées pour la démo ; ce que nous ferions en industriel (top 3 des [recommandations](governance/recommandations.md)) | Diaporama |

Le **Clip Chrono** n'est pas diffusé pendant les 5 minutes (il est rendu à part) : il sert de **plan B** si le live échoue.

## Le diaporama (8 diapos)

| # | Titre | Contenu | Source dans le dépôt |
|---|---|---|---|
| 1 | Resilience Alpha — groupe 16 | Nom du projet, les 5 membres, une ligne : « une plateforme de paiement qui se répare seule, et le prouve » | README §1 |
| 2 | Quand un paiement ne passe plus | Coût d'un arrêt (tableau 1 min / 15 min / 1 h), objectif < 3 min, principe : un conteneur qui redémarre n'est pas une preuve | [PCA/PRA §2](governance/pca-pra/README.md) |
| 3 | Démonstration | Ce qu'il faut regarder : les 4 phases du dashboard, le score ML, le journal de l'incident | [DEMARRAGE §9](../DEMARRAGE.md#9-lancer-la-démonstration-attaque-et-reprise-autonome) |
| 4 | Architecture et boucle de reprise | Schéma des 5 piliers et des réseaux ; schéma de la boucle (5 étapes) | README §2, [architecture](architecture/README.md) |
| 5 | Détection par machine learning | 6 indicateurs, données réelles (121 relevés), scores nominal 0,02 / dégradé 0,97, seuil 0,7 sur 3 relevés, limites | [ml/README](../ml/README.md) |
| 6 | Sécurité et privilèges | WAF/CRS, SOC, Vault, socket-proxy-rw, liste blanche, réseaux internes | README §12, [hardening](../security/hardening.md) |
| 7 | Gouvernance | EBIOS (scénario DoS), RTO visé / mesuré, NIS2/DORA, disponibilité ≠ compromission | [governance/](governance/) |
| 8 | Limites et recommandations | 3 limites assumées, 3 recommandations avec leur indicateur vérifiable | [recommandations](governance/recommandations.md) |

Le dashboard et le terminal de l'attaquant se montrent **en direct**, pas en capture : c'est ce que le jury vient voir.

## Avant de passer (30 minutes avant)

Check-list complète : [DEMARRAGE.md §12](../DEMARRAGE.md#12-jour-j--check-list-de-la-démonstration-et-du-clip-chrono). L'essentiel :

- [ ] Point d'accès `RESILIENCE-G16` actif, **économie d'énergie désactivée**, PC Attaquant connecté
- [ ] Stack complète `healthy`, réglages de démonstration dans `.env`, `ml_model_fallback = 0`
- [ ] Dashboard <http://127.0.0.1:5173> **rechargé** et en phase « Fonctionnement nominal » (aucun incident clos depuis 10 min)
- [ ] Frontal ouvert sur le PC Attaquant (<http://192.168.137.1>), commande d'attaque prête dans le terminal
- [ ] Une transaction manuelle `COMPLETED`, puis **plus personne ne touche au PC Hôte**
- [ ] Clip Chrono et vidéo de démonstration prêts à être lancés (plan B)

## Si quelque chose tourne mal

| Situation | Réaction |
|---|---|
| Rien ne se déclenche après 60 s | Laisser tourner (jusqu'à 75 s mesurés) ; sinon le dire, montrer le Clip Chrono et le journal d'un incident de la répétition |
| Le frontal ne répond plus | Point d'accès coupé : ne pas toucher au PC Hôte pendant le jury ; passer au Clip Chrono |
| Le jury veut relancer l'attaque | L'attaquant est banni 5 minutes après la reprise : c'est la défense qui fonctionne. L'expliquer, ou attendre la levée du ban |
| Incident en `FAILED` | Le dire franchement : la plateforme a escaladé vers un humain, comme prévu par le PCA/PRA. Ne pas réparer en direct (axe 1) |

## Questions probables (5 minutes)

| Question | Où est la réponse |
|---|---|
| Pourquoi l'Isolation Forest ? Sur quelles données ? Faux positifs ? | [ml/README](../ml/README.md) : résultats et limites, plancher de variabilité, réarmement |
| Pourquoi avoir relâché les limites de débit ? | [calibrage](test-results/calibrage-attaque-dos.md) : aux réglages normaux, le WAF absorbe et le SOC bannit en 5 s ; on relâche pour montrer la deuxième ligne de défense |
| Le moteur de remédiation a des droits élevés : comment sont-ils limités ? | README §10 et §12 : socket-proxy-rw, liste blanche, jamais sur `app-net`, webhooks HMAC / bearer |
| Que se passe-t-il si c'est une fuite de données, pas un DoS ? | [PCA/PRA §3 ter](governance/pca-pra/README.md) : chemin humain, rotation des secrets, notification |
| NIS2 ou DORA ? | [NIS2/DORA](governance/nis2-dora/README.md) : DORA s'applique, *lex specialis* |
| Qu'avez-vous mesuré ? | [répétition générale](test-results/repetition-generale.md) : 6/6, 37 à 75 s, 3 défauts trouvés et corrigés |
| Que feriez-vous en industriel ? | [recommandations](governance/recommandations.md) §4 |
| Avez-vous utilisé l'IA générative ? Qui maîtrise quoi ? | Oui (README §18) : chacun présente la partie du code qu'il a relue et testée |
| Et la biométrie (consigne 1) ? | Préparée, non activée par décision d'équipe : [biometrics/](../biometrics/README.md), activable par `BACKOFFICE_BIOMETRICS=true` |

## Répétitions (demain matin)

Trois passages complets chronométrés, **sans toucher au code** : la démonstration doit tenir dans le créneau 1:00 – 2:40. Noter les temps réels ici :

| Passage | Durée totale | Boucle (attaque → reprise) | Incident | Remarques |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
