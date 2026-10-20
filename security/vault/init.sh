#!/bin/sh
# Initialise Vault, le descelle, et y dépose les secrets de la plateforme.
#
# Ne JAMAIS afficher de secret : les clés d'unseal et le root token sont écrits dans le
# volume vault-init-out (jamais dans le dépôt), le token de service dans le volume vault-token.
# Idempotent : relançable à chaque démarrage (ré-unseal + ré-écriture des secrets).
#
# Variables attendues :
#   VAULT_ADDR         ex. http://vault:8200
#   JWT_SECRET         secret de signature JWT à déposer dans Vault
#   POSTGRES_PASSWORD  mot de passe BDD à déposer dans Vault
set -eu

OUT_DIR="${OUT_DIR:-/out}"          # clés d'unseal + root token (volume, hors dépôt)
TOKEN_DIR="${TOKEN_DIR:-/token}"    # token de service lu par auth-service / payment-api
INIT_FILE="$OUT_DIR/vault-init.json"
SERVICE_TOKEN_FILE="$TOKEN_DIR/service-token"

log() { echo "[vault-init] $1"; }

: "${VAULT_ADDR:?VAULT_ADDR manquant}"
: "${JWT_SECRET:?JWT_SECRET manquant}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD manquant}"
export VAULT_ADDR

# 1. Attendre que Vault réponde
i=0
until vault status -format=json >/dev/null 2>&1 || [ "$i" -ge 30 ]; do
  i=$((i + 1)); sleep 1
done

json_bool() { echo "$1" | grep -o "\"$2\": *[a-z]*" | grep -o '[a-z]*$'; }
status=$(vault status -format=json 2>/dev/null || true)
initialized=$(json_bool "$status" initialized)

# 2. Initialiser (une seule fois). 1 part de clé : simplification de DÉMO, à documenter.
if [ "$initialized" = "false" ]; then
  log "Initialisation de Vault (1 part de clé, usage démo)."
  umask 077
  mkdir -p "$OUT_DIR"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$INIT_FILE"
  chmod 600 "$INIT_FILE"
else
  log "Vault déjà initialisé."
  if [ ! -f "$INIT_FILE" ]; then
    log "ERREUR : Vault initialisé mais $INIT_FILE introuvable. Impossible de desceller."
    log "Remise à zéro nécessaire : docker compose down -v (efface les données Vault)."
    exit 1
  fi
fi

# Extraire la clé d'unseal et le root token du JSON (sans jq). Le JSON de Vault est
# multi-ligne : on l'aplatit d'abord. Une seule part de clé (démo), donc la première suffit.
flat=$(tr -d '\n' < "$INIT_FILE")
unseal_key=$(echo "$flat" | sed 's/.*"unseal_keys_b64": *\[ *"\([^"]*\)".*/\1/')
root_token=$(echo "$flat" | sed 's/.*"root_token": *"\([^"]*\)".*/\1/')

# 3. Desceller si besoin
if [ "$(json_bool "$status" sealed)" = "true" ] || [ "$initialized" = "false" ]; then
  log "Descellement."
  vault operator unseal "$unseal_key" >/dev/null
fi

# 4. S'authentifier (sans afficher le token)
vault login -no-print "$root_token"

# 5. Activer le moteur KV v2 (une fois)
if ! vault secrets list -format=json | grep -q '"secret/"'; then
  log "Activation du moteur KV v2 sur secret/."
  vault secrets enable -path=secret -version=2 kv
fi

# 6. Déposer les secrets (kv put n'affiche que la version, jamais la valeur)
log "Dépôt des secrets (payment, database)."
vault kv put secret/payment  jwt_secret="$JWT_SECRET"          >/dev/null
vault kv put secret/database postgres_password="$POSTGRES_PASSWORD" >/dev/null

# 7. Politique en lecture seule pour les services
vault policy write app-ro - <<'EOF' >/dev/null
path "secret/data/payment"  { capabilities = ["read"] }
path "secret/data/database" { capabilities = ["read"] }
EOF

# 8. Token de service (lecture seule, renouvelable), écrit dans un fichier, jamais affiché
umask 077
mkdir -p "$TOKEN_DIR"
# Réécriture : on supprime d'abord (le token précédent appartient à l'uid 10001, que root
# ne peut pas écraser sans CAP_DAC_OVERRIDE ; mais il possède le dossier, donc il peut délier).
rm -f "$SERVICE_TOKEN_FILE"
vault token create -policy=app-ro -period=24h -field=token > "$SERVICE_TOKEN_FILE"
chmod 640 "$SERVICE_TOKEN_FILE"
# Lisible par l'uid 10001 (auth-service, payment-api) quand le script tourne en root
chown 10001:10001 "$SERVICE_TOKEN_FILE" 2>/dev/null || true

log "Terminé : secrets déposés, token de service écrit dans $SERVICE_TOKEN_FILE."
log "Clés d'unseal et root token dans $INIT_FILE (volume, hors dépôt)."
