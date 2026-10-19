import { useCallback, useEffect, useState } from 'react'
import { incidents, query, queryRange, QUERIES, RANGE_QUERIES } from './api.js'
import { formatLatency, formatPercent, formatRate, formatScore, formatTime } from './format.js'
import { computePhase, scalar, toPoints, toTargets } from './status.js'
import Incidents from './components/Incidents.jsx'
import LineChart from './components/LineChart.jsx'
import PhaseBanner from './components/PhaseBanner.jsx'
import StatTile from './components/StatTile.jsx'
import Targets from './components/Targets.jsx'

const REFRESH_MS = 5000

const EMPTY = {
  prometheusOk: false,
  values: {},
  series: {},
  targets: [],
  incidents: { available: false, items: [] },
  updatedAt: null,
}

async function load() {
  const names = Object.keys(QUERIES)
  const [instant, ranges, remediation] = await Promise.all([
    Promise.allSettled(names.map((name) => query(QUERIES[name]))),
    Promise.allSettled(RANGE_QUERIES.map((name) => queryRange(QUERIES[name]))),
    incidents(),
  ])
  const ok = instant.some((r) => r.status === 'fulfilled')
  const get = (i) => (instant[i].status === 'fulfilled' ? instant[i].value : [])
  return {
    prometheusOk: ok,
    values: Object.fromEntries(names.filter((n) => n !== 'targets').map((n) => [n, scalar(get(names.indexOf(n)))])),
    series: Object.fromEntries(RANGE_QUERIES.map((n, i) => [n, ranges[i].status === 'fulfilled' ? toPoints(ranges[i].value) : []])),
    targets: toTargets(get(names.indexOf('targets'))),
    incidents: remediation,
    updatedAt: Date.now() / 1000,
  }
}

export default function App() {
  const [state, setState] = useState(EMPTY)

  const refresh = useCallback(async () => {
    try {
      setState(await load())
    } catch {
      setState((previous) => ({ ...previous, prometheusOk: false }))
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(() => {
      if (!document.hidden) refresh() // pas de requêtes quand l'onglet est en arrière-plan
    }, REFRESH_MS)
    return () => clearInterval(timer)
  }, [refresh])

  const { values, series } = state
  const phase = computePhase({
    prometheusOk: state.prometheusOk,
    canaryUp: values.canaryUp ?? null,
    successRatio: values.successRatio ?? null,
    incidents: state.incidents.items,
  })
  const upCount = state.targets.filter((t) => t.up).length
  const mlReady = values.mlScore !== null && values.mlScore !== undefined

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Supervision de la plateforme de paiement</h1>
          <p className="muted text-sm">Resilience Alpha - groupe 16 - données fictives</p>
        </div>
        <p className="muted text-sm" aria-live="polite">
          {state.updatedAt ? `Mis à jour à ${formatTime(state.updatedAt)}, toutes les 5 secondes` : 'Chargement des données...'}
        </p>
      </header>

      <PhaseBanner phase={phase} />

      <section aria-label="Chiffres clés" className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Canari" value={values.canaryUp === 1 ? 'OK' : values.canaryUp === 0 ? 'En échec' : '-'} detail="Dernière transaction" />
        <StatTile label="Taux de succès" value={formatPercent(values.successRatio)} detail="Canari, 60 dernières secondes" />
        <StatTile label="Latence p95" value={formatLatency(values.latencyP95)} detail="Transaction canari" />
        <StatTile label="Débit" value={formatRate(values.throughput)} detail="Transactions traitées" />
        <StatTile label="Erreurs 5xx" value={values.errors5xx === null || values.errors5xx === undefined ? '-' : `${formatScore(values.errors5xx)} /s`} detail="Toutes API" />
        <StatTile label="Score d'anomalie" value={mlReady ? formatScore(values.mlScore) : 'En attente'} detail={mlReady ? `Seuil ${formatScore(values.mlThreshold)}` : 'Détecteur ML non déployé'} />
      </section>

      <section aria-label="Évolution sur 15 minutes" className="grid gap-3 lg:grid-cols-2">
        <LineChart title="Taux de succès du canari" points={series.successRatio ?? []} format={formatPercent} yMax={1} emptyText="Pas encore de mesure du canari." />
        <LineChart title="Latence p95 du canari" points={series.latencyP95 ?? []} format={formatLatency} emptyText="Pas encore de mesure de latence." />
        <LineChart title="Débit de transactions" points={series.throughput ?? []} format={formatRate} emptyText="Aucune transaction sur la période." />
        <LineChart
          title="Score d'anomalie (Isolation Forest)"
          points={series.mlScore ?? []}
          format={formatScore}
          yMax={1}
          threshold={mlReady && values.mlThreshold !== null ? { value: values.mlThreshold, label: 'Seuil' } : undefined}
          emptyText="Le détecteur ML n'est pas encore déployé."
        />
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <Targets targets={state.targets} />
        <Incidents data={state.incidents} />
      </div>

      <footer className="muted text-xs">
        {upCount} service(s) sur {state.targets.length} répondent à Prometheus. Console d'administration, accessible
        uniquement depuis le PC Hôte (127.0.0.1).
      </footer>
    </div>
  )
}
