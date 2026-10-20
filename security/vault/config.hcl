# Configuration Vault (mode production, stockage fichier).
# Vault n'a AUCUN port publié : il n'est joignable que sur data-net (auth-service, payment-api).

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  # TLS désactivé : réseau Docker interne uniquement (data-net), pas d'exposition.
  # En production hors labo, activer TLS ici.
  tls_disable = "true"
}

# mlock activé (le conteneur a la capacité IPC_LOCK) : empêche la mise en swap des secrets.
disable_mlock = false

# Interface web inutile (aucun port publié) : réduit la surface.
ui = false

api_addr = "http://vault:8200"
