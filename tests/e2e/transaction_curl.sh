#!/bin/sh
# Transaction fictive de bout en bout, exécutée DANS un conteneur curl relié à app-net
# (les API n'ont aucun port publié). Usage depuis PowerShell : voir README.md, section 7.5.
#
# Variables : PASS (mot de passe de demo, obligatoire), FROM, TO, AMOUNT (facultatives).
set -eu

: "${PASS:?Variable PASS manquante : mot de passe de l'utilisateur demo}"
FROM="${FROM:-ACC-001}"
TO="${TO:-ACC-002}"
AMOUNT="${AMOUNT:-10.50}"

TOKEN=$(curl -sf -X POST http://auth-service:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo\",\"password\":\"$PASS\"}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "Échec : authentification refusée (mot de passe ou auth-service indisponible)" >&2
  exit 1
fi
echo "1. Authentification : OK"

echo "2. Solde $FROM avant : $(curl -s "http://payment-api:8000/accounts/$FROM" -H "Authorization: Bearer $TOKEN")"

RESULT=$(curl -s -X POST http://payment-api:8000/transactions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"from_account\":\"$FROM\",\"to_account\":\"$TO\",\"amount\":\"$AMOUNT\",\"currency\":\"EUR\"}")
echo "3. Virement de $AMOUNT EUR $FROM vers $TO : $RESULT"

echo "4. Solde $FROM après : $(curl -s "http://payment-api:8000/accounts/$FROM" -H "Authorization: Bearer $TOKEN")"

case "$RESULT" in
  *'"status":"COMPLETED"'*) echo "Résultat : COMPLETED" ;;
  *) echo "Résultat : la transaction n'est pas COMPLETED" >&2; exit 1 ;;
esac
