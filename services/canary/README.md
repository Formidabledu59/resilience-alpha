# canary

Sonde métier : prouve que la plateforme sait encore **traiter un paiement**, pas seulement qu'un conteneur tourne. Contrat complet : [`docs/architecture/contracts.md`](../../docs/architecture/contracts.md).

- Toutes les `CANARY_INTERVAL_SECONDS` : token (mis en cache) puis transaction de 1 EUR entre `CANARY-A` et `CANARY-B`, en alternant le sens après chaque succès pour ne jamais vider les comptes
- Succès = `201` avec `status: COMPLETED`. Tout le reste est un échec
- `POST /probe` : transaction de contrôle immédiate, utilisée par `remediation-engine` pour clôturer un incident
- Métriques : `canary_up`, `canary_success_ratio` (60 s), `canary_latency_seconds`, `canary_transactions_total{result}`
- `GET /health` (processus vivant uniquement), port `8000`

Variables : `AUTH_URL`, `PAYMENT_URL` (directement les services pour le POC, le WAF plus tard), `AUTH_CANARY_PASSWORD`, `CANARY_INTERVAL_SECONDS`.

## Tests

Auth-service et payment-api sont simulés, aucun réseau n'est nécessaire :

```bash
cd services/canary
pip install -r requirements.txt pytest
pytest
```
