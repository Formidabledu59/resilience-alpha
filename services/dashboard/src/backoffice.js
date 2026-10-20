// Logique pure du flux de connexion au back-office (testable sans React).
// Traduit la réponse de la passerelle en prochaine étape + message pour l'utilisateur.

export function nextAfterIdentify(result) {
  switch (result.status) {
    case 'recognized':
      return { step: 'password', message: 'Visage reconnu. Saisissez votre mot de passe.', tone: 'ok' }
    case 'not_recognized': {
      const reste = result.attempts_left === 1 ? ' Un dernier essai avant blocage.' : ''
      return { step: 'username', clearUsername: true, message: `Visage non reconnu.${reste}`, tone: 'error' }
    }
    case 'locked':
      return {
        step: 'username',
        clearUsername: true,
        message: `Trop de tentatives. Reessayez dans ${result.retry_in} secondes.`,
        tone: 'error',
      }
    default:
      return { step: 'username', clearUsername: true, message: 'Erreur de reconnaissance.', tone: 'error' }
  }
}

export function nextAfterPassword(result) {
  switch (result.status) {
    case 'granted':
      return { step: 'granted', message: 'Acces accorde.', tone: 'ok' }
    case 'denied':
      return { step: 'username', clearUsername: true, message: 'Mot de passe incorrect. On recommence.', tone: 'error' }
    case 'face_first':
      return { step: 'username', clearUsername: true, message: 'Reconnaissance faciale requise.', tone: 'error' }
    default:
      return { step: 'username', clearUsername: true, message: 'Erreur.', tone: 'error' }
  }
}
