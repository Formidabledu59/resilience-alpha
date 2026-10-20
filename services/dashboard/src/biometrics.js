// Appels à la passerelle biométrique (service natif du PC Hôte), relayés par le nginx
// du dashboard vers host.docker.internal. Le navigateur ne parle qu'à la même origine.

const TIMEOUT_MS = 20000   // la reconnaissance faciale peut prendre quelques secondes

async function call(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(`/api/biometrics${path}`, {
      ...options,
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      signal: controller.signal,
    })
    if (!response.ok && response.status !== 423) {
      throw new Error(`HTTP ${response.status}`)
    }
    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}

export const identify = (username) =>
  call('/identify', { method: 'POST', body: JSON.stringify({ username }) })

export const submitPassword = (username, password) =>
  call('/password', { method: 'POST', body: JSON.stringify({ username, password }) })

export const listUsers = () => call('/users')

export const enroll = (username, password) =>
  call('/enroll', { method: 'POST', body: JSON.stringify({ username, password }) })

export const revoke = (username) =>
  call(`/users/${encodeURIComponent(username)}`, { method: 'DELETE' })

const KEY = 'backoffice-auth'

export function loadAuth() {
  try {
    const value = JSON.parse(sessionStorage.getItem(KEY))
    if (value && value.expiresAt > Date.now()) return value
  } catch {
    // stockage indisponible
  }
  return null
}

export function saveAuth(username) {
  const value = { username, expiresAt: Date.now() + 30 * 60 * 1000 }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    // sans stockage, la session vit en mémoire seulement
  }
  return value
}

export function clearAuth() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // rien à nettoyer
  }
}
