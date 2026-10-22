# payment-api

Crée et consulte des transactions fictives dans PostgreSQL. Contrat complet : [`docs/architecture/contracts.md`](../../docs/architecture/contracts.md).

- `POST /transactions` (Bearer JWT) → `201 {id, status}` : `COMPLETED`, ou `REJECTED` si le solde est insuffisant
- `GET /transactions/{id}`, `GET /accounts/{id}` (Bearer JWT)
- Débit et crédit dans une seule transaction SQL, comptes verrouillés (`FOR UPDATE`) dans un ordre fixe
- Au démarrage : création des tables `accounts` / `transactions` et des comptes `ACC-001`, `ACC-002`, `CANARY-A`, `CANARY-B`
- Métriques : `payment_transactions_total{status}` + latence HTTP. `GET /health`, port `8000`

Variables : `JWT_SECRET`, `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `VAULT_ADDR`, `VAULT_TOKEN_FILE`. Quand le profile `security` tourne, `JWT_SECRET` et `POSTGRES_PASSWORD` sont lus dans Vault (`secret/payment` et `secret/database`) ; sinon dans les variables d'environnement.

## Tests

Les tests ne nécessitent pas de base de données (authentification, validation, métriques) :

```bash
cd services/payment-api
pip install -r requirements.txt pytest
pytest
```
