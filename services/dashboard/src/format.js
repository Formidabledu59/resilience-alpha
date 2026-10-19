// Formatage français. Intl insère des espaces insécables (codes 0xA0 et 0x202F) :
// on les remplace par des espaces normales, règle typographique du projet.
const NON_BREAKING_SPACES = new RegExp(`[${String.fromCodePoint(0xa0, 0x202f)}]`, 'g')
const clean = (text) => text.replace(NON_BREAKING_SPACES, ' ')

function number(value, digits) {
  return clean(new Intl.NumberFormat('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value))
}

export function formatPercent(ratio) {
  if (ratio === null || ratio === undefined) return '-'
  return `${number(ratio * 100, 1)} %`
}

export function formatLatency(seconds) {
  if (seconds === null || seconds === undefined) return '-'
  return seconds < 1 ? `${number(seconds * 1000, 0)} ms` : `${number(seconds, 2)} s`
}

export function formatRate(perSecond) {
  if (perSecond === null || perSecond === undefined) return '-'
  return `${number(perSecond, 2)} tx/s`
}

export function formatScore(score) {
  if (score === null || score === undefined) return '-'
  return number(score, 2)
}

export function formatTime(seconds) {
  return clean(new Date(seconds * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
}
