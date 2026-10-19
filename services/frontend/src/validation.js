// Validation côté navigateur. payment-api revalide tout côté serveur :
// ces contrôles servent au confort de l'utilisateur, pas à la sécurité.

export const ACCOUNTS = ['ACC-001', 'ACC-002']
export const MAX_AMOUNT = 10000

// "10", "10.5", "10,50" -> "10.50" ; sinon null
export function parseAmount(raw) {
  const text = String(raw ?? '').trim().replace(',', '.')
  if (!/^\d{1,7}(\.\d{1,2})?$/.test(text)) return null
  const value = Number(text)
  if (!Number.isFinite(value)) return null
  return value.toFixed(2)
}

export function validateLogin({ username, password }) {
  const errors = {}
  if (!username || !username.trim()) errors.username = "Saisissez votre identifiant."
  else if (username.length > 64) errors.username = "L'identifiant est trop long."
  if (!password) errors.password = 'Saisissez votre mot de passe.'
  return errors
}

export function validatePayment({ from, to, amount }) {
  const errors = {}
  if (!ACCOUNTS.includes(from)) errors.from = 'Choisissez le compte à débiter.'
  if (!ACCOUNTS.includes(to)) errors.to = 'Choisissez le compte à créditer.'
  else if (from === to) errors.to = 'Le compte à créditer doit être différent du compte débité.'

  const normalized = parseAmount(amount)
  if (normalized === null) errors.amount = 'Saisissez un montant valide, par exemple 12,50.'
  else if (Number(normalized) <= 0) errors.amount = 'Le montant doit être supérieur à 0.'
  else if (Number(normalized) > MAX_AMOUNT) errors.amount = `Le montant ne peut pas dépasser ${MAX_AMOUNT} EUR.`

  if (Object.keys(errors).length > 0) return { errors, payload: null }
  return { errors, payload: { from_account: from, to_account: to, amount: normalized, currency: 'EUR' } }
}

// Anti-spam : un humain ne voit pas le champ piège, un robot le remplit
export function isSpam(honeypot) {
  return typeof honeypot === 'string' && honeypot.trim() !== ''
}

// Espaces insécables (codes 0xA0 et 0x202F) produites par Intl
const NON_BREAKING_SPACES = new RegExp(`[${String.fromCodePoint(0xa0, 0x202f)}]`, 'g')

export function formatEuros(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  // Intl place une espace insécable avant "EUR" : on la remplace par une espace normale
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
    .format(number)
    .replace(NON_BREAKING_SPACES, ' ')
}
