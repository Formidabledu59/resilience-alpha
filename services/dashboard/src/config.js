// Configuration lue au chargement : /config.json est généré par nginx au démarrage du conteneur
// à partir de .env (BACKOFFICE_BIOMETRICS), pour activer ou non la porte biométrique sans
// recompiler le dashboard.

// La porte n'est active que si la configuration le demande explicitement (true).
// Biométrie (consigne additionnelle 1) préparée mais désactivée par défaut pour la démonstration.
export function biometricsEnabled(config) {
  return config?.backofficeBiometrics === true
}

// En cas d'absence ou d'erreur (serveur de développement Vite, fichier illisible), on renvoie
// une configuration vide : la supervision s'affiche, sans appel à la passerelle.
export async function loadConfig(fetchImpl = fetch) {
  try {
    const response = await fetchImpl('/config.json', { cache: 'no-store' })
    if (!response.ok) return {}
    return await response.json()
  } catch {
    return {}
  }
}
