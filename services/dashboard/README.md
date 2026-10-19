# dashboard

Tableau de bord de supervision de la démonstration (React 19 + Tailwind CSS 4, build Vite), servi par nginx non-root (uid 101).
Publié sur **`http://127.0.0.1:5173`** uniquement (PC Hôte). Rafraîchissement toutes les 5 secondes, en pause quand l'onglet est caché.

## Ce qu'il affiche

| Zone | Contenu | Source |
|---|---|---|
| Bandeau de phase | Avant / Pendant / Remédiation / Après, avec icône et libellé | canary + incidents de la remédiation |
| Chiffres clés | Canari, taux de succès 60 s, latence p95, débit, erreurs 5xx, score d'anomalie | Prometheus |
| Courbes 15 min | Taux de succès, latence p95, débit, score d'anomalie (avec seuil) | Prometheus (`query_range`) |
| Services surveillés | Cibles UP / DOWN | Prometheus (`up`) |
| Incidents | Étapes de remédiation en direct | `remediation-engine` (`GET /incidents`) |
| Action principale | « Lancer une transaction de contrôle » | `canary` (`POST /probe`) |

Règles de la phase (`src/status.js`, testées) :

| Phase | Condition |
|---|---|
| Remédiation | un incident `OPEN`, `REMEDIATING` ou `VERIFYING` |
| Pendant (incident) | `canary_up == 0` ou taux de succès inférieur à 80 % |
| Pendant (dégradé) | taux de succès entre 80 % et 99 % |
| Après | incident clôturé depuis moins de 10 minutes et service nominal |
| Avant | fonctionnement nominal |

Les zones « Score d'anomalie » et « Incidents » affichent un message d'attente tant que `ml-detector` et `remediation-engine` ne sont pas déployés.

## Relais nginx (lecture seule, sauf la transaction de contrôle)

| URL du navigateur | Cible | Méthode |
|---|---|---|
| `/api/prometheus/query` | `prometheus:9090/api/v1/query` | GET |
| `/api/prometheus/query_range` | `prometheus:9090/api/v1/query_range` | GET |
| `/api/canary/probe` | `canary:8000/probe` | POST, 6 par minute |
| `/api/remediation/incidents` | `remediation-engine:8000/incidents` | GET |

Tout autre chemin `/api/` renvoie 404. Le dashboard n'a aucun accès à Docker, Vault ou aux secrets (vérifié par un test). Le DNS Docker est résolu à chaque requête : nginx démarre même si un service n'existe pas encore.

## Visualisation

- Une seule série par courbe : le titre la nomme, pas de légende.
- Survol : réticule et infobulle. Vue tableau (« Voir les valeurs ») sous chaque courbe.
- Couleurs par rôle (`src/index.css`), mode clair et mode sombre (suit le système). Les couleurs de statut sont réservées aux états et toujours accompagnées d'une icône et d'un libellé.
- SVG fait main : aucune bibliothèque de graphiques à charger (JS 74 Ko après gzip).

## Tests

```powershell
docker run --rm -v "${PWD}/services/dashboard:/app" -v resilience-db-nm:/app/node_modules -w /app node:22.23.3-alpine3.24 sh -c "npm install -g npm@11.21.0 && npm ci && npm test && npm run build"
```

Tests : phases de la démonstration, lecture des réponses Prometheus, formatage français, correspondance entre les URL appelées et les relais nginx, typographie.
