// Accès aux données. Le navigateur n'appelle que /api/* sur la même origine ;
// le nginx du dashboard relaie, en lecture seule, vers Prometheus, le canary et la remédiation.

const TIMEOUT_MS = 5000

export const QUERIES = {
  canaryUp: 'canary_up',
  successRatio: 'canary_success_ratio',
  latencyP95: 'histogram_quantile(0.95, sum by (le) (rate(canary_latency_seconds_bucket[1m])))',
  throughput: 'sum(rate(payment_transactions_total[1m]))',
  errors5xx: 'sum(rate(http_requests_total{status="5xx"}[1m])) or vector(0)',
  mlScore: 'max(ml_anomaly_score)',
  mlThreshold: 'max(ml_anomaly_threshold)',
  targets: 'up',
}

// Séries tracées sur les 15 dernières minutes
export const RANGE_QUERIES = ['successRatio', 'latencyP95', 'throughput', 'mlScore']
export const RANGE_SECONDS = 15 * 60
export const RANGE_STEP = 15

async function getJson(url, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(url, { ...options, headers: { Accept: 'application/json' }, signal: controller.signal })
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}`)
      error.status = response.status
      throw error
    }
    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}

export async function query(promql) {
  const body = await getJson(`/api/prometheus/query?query=${encodeURIComponent(promql)}`)
  return body.data.result
}

export async function queryRange(promql, end = Date.now() / 1000) {
  const params = new URLSearchParams({
    query: promql,
    start: String(Math.floor(end - RANGE_SECONDS)),
    end: String(Math.floor(end)),
    step: String(RANGE_STEP),
  })
  const body = await getJson(`/api/prometheus/query_range?${params}`)
  return body.data.result
}

// Journal des incidents. Si le moteur de remédiation n'est pas démarré, on renvoie
// "indisponible" au lieu d'une erreur, et l'intégrité du journal reste inconnue (null).
export async function incidents() {
  const [items, integrity] = await Promise.allSettled([
    getJson('/api/remediation/incidents?limit=20'),
    getJson('/api/remediation/journal/verify'),
  ])
  if (items.status !== 'fulfilled') return { available: false, items: [], integrity: null }
  return { available: true, items: items.value, integrity: integrity.status === 'fulfilled' ? integrity.value : null }
}

// Rapport Markdown d'un incident, téléchargé par un simple lien
export function reportUrl(incidentId) {
  return `/api/remediation/incidents/${encodeURIComponent(incidentId)}/report`
}

export async function probe() {
  return getJson('/api/canary/probe', { method: 'POST' })
}
