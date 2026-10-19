# auth-service

Émet les JWT de la plateforme de paiement fictive. Contrat complet : [`docs/architecture/contracts.md`](../../docs/architecture/contracts.md).

- `POST /auth/token` `{username, password}` → `{access_token, token_type: "bearer", expires_in: 900}`
- JWT HS256 signé avec `JWT_SECRET`, valable 15 minutes (Vault remplacera la variable plus tard)
- Deux utilisateurs fictifs, en mémoire, mots de passe hashés en PBKDF2-SHA256 au démarrage : `demo` (`AUTH_DEMO_PASSWORD`) et `canary` (`AUTH_CANARY_PASSWORD`)
- `GET /health`, `GET /metrics` (latence HTTP), port `8000`

Le service refuse de démarrer si une des trois variables manque.

## Tests

```bash
cd services/auth-service
pip install -r requirements.txt pytest
pytest
```
