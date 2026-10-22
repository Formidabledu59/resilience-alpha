# Résultats d'essais

> Comptes rendus des essais et campagnes de chaos engineering du démonstrateur Resilience Alpha.
> Données fictives, cadre laboratoire.

| Document | Objet | Conclusion |
|---|---|---|
| [`repetition-boucle-reprise.md`](repetition-boucle-reprise.md) | Répétition de la boucle de reprise en conteneurs (arrêt d'un service) | Reprise autonome prouvée en ~67 s (transaction de contrôle COMPLETED) |
| [`calibrage-attaque-dos.md`](calibrage-attaque-dos.md) | Calibrage de l'attaque DoS applicative | WAF absorbe la charge ; calibrage réseau à finaliser pour déclencher le chemin ML |

## Convention

Chaque essai note : la date et le contexte (poste, réseau, réglages), la question posée, la
méthode, les mesures, la conclusion, et les points restant à traiter. Les essais rejouables sont
reliés à leur script (`attack/`, `tests/e2e/`) ou à leur procédure (`docs/runbooks/`).

## À compléter

- Scénario de bout en bout `tests/e2e/resilience_scenario.py` rejoué depuis le PC Attaquant, sur
  le réseau `RESILIENCE-G16`, avec un DoS calibré déclenchant le détecteur ML.
- Essai de l'assistant RAG avec Ollama lancé (qualité des réponses, sources citées).
