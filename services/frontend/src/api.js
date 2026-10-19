// Appels aux API. Le navigateur ne parle qu'à /api/* sur la même origine :
// le serveur du frontal (nginx) relaie vers auth-service et payment-api.
// Aucun secret dans le code du navigateur.

const TIMEOUT_MS = 8000
const SESSION_KEY = 'resilience-session'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

const MESSAGES = {
  401: 'Votre session a expiré. Reconnectez-vous.',
  404: 'Compte introuvable.',
  422: 'Les informations envoyées sont invalides.',
  429: 'Trop de tentatives. Patientez une minute avant de réessayer.',
}

async function request(path, { method = 'GET', body, token } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const headers = { Accept: 'application/json' }
    if (body) headers['Content-Type'] = 'application/json'
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      throw new ApiError(response.status, MESSAGES[response.status] ?? 'Le service est momentanément indisponible.')
    }
    return data
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(0, 'Le service est momentanément indisponible. Réessayez dans quelques secondes.')
  } finally {
    clearTimeout(timer)
  }
}

export async function login(username, password) {
  try {
    return await request('/auth/token', { method: 'POST', body: { username, password } })
  } catch (error) {
    if (error.status === 401) throw new ApiError(401, 'Identifiant ou mot de passe incorrect.')
    throw error
  }
}

export const createTransaction = (token, payload) => request('/transactions', { method: 'POST', body: payload, token })
export const getAccount = (token, id) => request(`/accounts/${encodeURIComponent(id)}`, { token })

// Session conservée le temps de l'onglet uniquement (sessionStorage, pas de cookie)
export function loadSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY))
    if (session && session.expiresAt > Date.now()) return session
  } catch {
    // stockage indisponible (navigation privée stricte) : pas de session
  }
  clearSession()
  return null
}

export function saveSession(username, tokenResponse) {
  const session = {
    username,
    token: tokenResponse.access_token,
    expiresAt: Date.now() + tokenResponse.expires_in * 1000,
  }
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    // sans stockage, la session vit seulement en mémoire
  }
  return session
}

export function clearSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // rien à nettoyer
  }
}
