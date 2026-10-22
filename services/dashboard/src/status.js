// Logique d'état du tableau de bord, sans React : testée unitairement.

export const ACTIVE_INCIDENT_STATUSES = ['OPEN', 'REMEDIATING', 'VERIFYING']
const RECOVERY_WINDOW_SECONDS = 10 * 60
const NOMINAL_RATIO = 0.99
const INCIDENT_RATIO = 0.8
// Le taux de succès est calculé sur 60 s : juste après la clôture d'un incident (reprise prouvée
// par une transaction de contrôle), il reste bas une minute alors que le canari réussit déjà.
// Pendant ce délai, on se fie au canari et à la clôture de l'incident (répétition du 22/10).
const STALE_RATIO_SECONDS = 90

export const PHASES = {
  unknown: { tone: 'neutral', icon: 'question', label: 'Données indisponibles', step: null },
  nominal: { tone: 'good', icon: 'check', label: 'Fonctionnement nominal', step: 'Avant' },
  degraded: { tone: 'warning', icon: 'warning', label: 'Service dégradé', step: 'Pendant' },
  incident: { tone: 'critical', icon: 'cross', label: 'Incident en cours', step: 'Pendant' },
  remediation: { tone: 'serious', icon: 'wrench', label: 'Remédiation automatique en cours', step: 'Remédiation' },
  recovered: { tone: 'good', icon: 'check', label: 'Reprise confirmée', step: 'Après' },
}

// Valeur numérique d'un résultat d'instant Prometheus (null si absent)
export function scalar(result) {
  if (!Array.isArray(result) || result.length === 0) return null
  const value = Number(result[0].value?.[1])
  return Number.isFinite(value) ? value : null
}

// Résultat de query_range -> [{ t: secondes, v: nombre }] (première série)
export function toPoints(result) {
  if (!Array.isArray(result) || result.length === 0) return []
  return result[0].values
    .map(([t, v]) => ({ t: Number(t), v: Number(v) }))
    .filter((point) => Number.isFinite(point.v))
}

export function toTargets(result) {
  if (!Array.isArray(result)) return []
  return result
    .map((item) => ({ job: item.metric.job, up: item.value[1] === '1' }))
    .sort((a, b) => a.job.localeCompare(b.job))
}

export function computePhase({ prometheusOk, canaryUp, successRatio, incidents = [], now = Date.now() / 1000 }) {
  if (!prometheusOk) return 'unknown'
  if (incidents.some((incident) => ACTIVE_INCIDENT_STATUSES.includes(incident.status))) return 'remediation'
  if (canaryUp === 0) return 'incident'
  const closedSince = (seconds) => incidents.some(
    (incident) => incident.status === 'CLOSED' && incident.closed_at && now - Date.parse(incident.closed_at) / 1000 < seconds,
  )
  if (canaryUp === 1 && closedSince(STALE_RATIO_SECONDS)) return 'recovered'
  if (successRatio !== null && successRatio < INCIDENT_RATIO) return 'incident'
  if (successRatio !== null && successRatio < NOMINAL_RATIO) return 'degraded'
  if (closedSince(RECOVERY_WINDOW_SECONDS)) return 'recovered'
  if (canaryUp === null) return 'unknown'
  return 'nominal'
}
