# Résultats d'essais

> Comptes rendus des essais et campagnes de chaos engineering du démonstrateur Resilience Alpha.
> Données fictives, cadre laboratoire.

| Document | Objet | Conclusion |
|---|---|---|
| [`repetition-boucle-reprise.md`](repetition-boucle-reprise.md) | Répétition de la boucle de reprise en conteneurs (arrêt d'un service) | Reprise autonome prouvée en ~67 s (transaction de contrôle COMPLETED) |
| [`calibrage-attaque-dos.md`](calibrage-attaque-dos.md) | Calibrage de l'attaque DoS applicative (22/10, point d'accès actif) | Réglages par défaut : WAF absorbe, SOC bannit en ~5 s. Limites relâchées, concurrence 200 : alerte ML (0,78) |
| [`repetition-generale.md`](repetition-generale.md) | Répétition générale chronométrée, 4 séries de 3 essais (22/10), puis vidéo de démonstration | **6/6 réussis** sur les deux dernières séries, détection ML, 37 à 75 s ; défauts trouvés et corrigés ; vidéo : incident clos 36 s après l'alerte, attaquant banni |

## Convention

Chaque essai note : la date et le contexte (poste, réseau, réglages), la question posée, la
méthode, les mesures, la conclusion, et les points restant à traiter. Les essais rejouables sont
reliés à leur script (`attack/`, `tests/e2e/`) ou à leur procédure (`docs/runbooks/`).

## À compléter

- **Attaque lancée depuis le PC Attaquant** (poste distinct, connecté à `RESILIENCE-G16`), exigée
  par le sujet. Les essais du 22/10 envoyaient l'attaque depuis le PC Hôte vers sa propre adresse
  `192.168.137.1` : même chemin réseau jusqu'au WAF, mais la latence du WiFi peut modifier le
  calibrage. Commande : `python attack/dos/flood.py --target http://192.168.137.1 --auth demo --duration 90 --concurrency 200`.
- Essai de l'assistant RAG avec Ollama lancé (qualité des réponses, sources citées).
