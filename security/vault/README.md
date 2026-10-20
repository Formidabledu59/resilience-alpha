# security/vault : gestion des secrets

HashiCorp Vault stocke les secrets de la plateforme. `auth-service` et `payment-api` les lisent depuis Vault, plus depuis le code ou le compose. Vault n'a **aucun port publié** : il n'est joignable que sur `data-net`.

| Fichier | Rôle |
|---|---|
| `config.hcl` | Config du serveur (stockage fichier, écoute sur 8200, mlock activé via `IPC_LOCK`) |
| `init.sh` | Initialise, descelle et dépose les secrets. Idempotent. N'affiche **aucun** secret |

## Secrets stockés (KV v2, moteur `secret/`)

| Chemin | Champ | Utilisé par |
|---|---|---|
| `secret/payment` | `jwt_secret` | auth-service (signe les JWT), payment-api (les vérifie) |
| `secret/database` | `postgres_password` | payment-api (connexion à la base) |

## Comment ça démarre

Le service `vault-init` (profile `security`) s'exécute une fois, après que Vault est sain, puis s'arrête :

1. initialise Vault (1 part de clé - **simplification de démo**, en production 5 parts / seuil 3) ;
2. le descelle ;
3. active le moteur KV v2 sur `secret/` ;
4. y dépose `jwt_secret` et `postgres_password` (valeurs issues de l'environnement de `vault-init`, pour correspondre à ce que postgres attend) ;
5. écrit une politique `app-ro` en **lecture seule** sur ces deux secrets ;
6. crée un token de service (politique `app-ro`, renouvelable 24 h) dans le volume `vault-token`.

`auth-service` et `payment-api` attendent la fin de `vault-init` (`service_completed_successfully`), lisent le token dans `/vault-token/service-token`, puis récupèrent leurs secrets depuis Vault. Au démarrage, ils journalisent la source :

```
[secrets] JWT_SECRET chargé depuis Vault (secret/payment:jwt_secret)
[secrets] POSTGRES_PASSWORD chargé depuis Vault (secret/database:postgres_password)
```

## Où sont les secrets sensibles de Vault

| Donnée | Emplacement | Jamais |
|---|---|---|
| Clés d'unseal + root token | volume `vault-init-out`, fichier `/out/vault-init.json` (mode 600) | affichés, ni dans le dépôt |
| Token de service (lecture seule) | volume `vault-token`, `/vault-token/service-token` (lisible par l'uid 10001) | affiché |
| `jwt_secret`, `postgres_password` | dans Vault (volume `vault-data`) | affichés par `init.sh` |

Ces volumes Docker ne sont pas dans le dépôt. `init.sh` ne fait qu'écrire dans des fichiers et rediriger les sorties sensibles : il n'imprime jamais une clé, un token ou un mot de passe.

## Repli sur l'environnement

Si le token de service est absent (profile `app` seul, sans Vault) ou si Vault ne répond pas, les services lisent les secrets depuis les variables d'environnement. Le profile `app` fonctionne donc sans Vault. En production, on retirerait ce repli pour imposer Vault (`services/*/vault_client.py`).

## Lancer

```powershell
docker compose up -d
docker compose --profile app --profile security up -d --build
```

Après démarrage, vérifier la source des secrets :

```powershell
docker compose logs auth-service payment-api | Select-String "\[secrets\]"
```

Relancer `vault-init` (par exemple après `docker compose down` sans `-v`) le ré-descelle et redépose les secrets, sans réinitialiser (idempotent). Après `docker compose down -v`, Vault repart de zéro (nouvelle initialisation).

## Limites connues (démo)

- **1 part de clé d'unseal** : simple pour la démo. En production, plusieurs parts réparties entre personnes.
- **TLS désactivé** sur l'écoute Vault : acceptable car `data-net` est interne et sans port publié. En production, activer TLS.
- **Descellement automatique** par `vault-init` qui lit la clé depuis un volume : pratique pour la démo, mais la clé d'unseal et le descellement ne doivent pas être automatisés ainsi en production (auto-unseal via KMS/HSM à la place).
