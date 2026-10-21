import { formatTime } from '../format.js'
import Icon from './Icon.jsx'

export const STATUS = {
  OPEN: { tone: 'critical', icon: 'cross', label: 'Ouvert' },
  REMEDIATING: { tone: 'serious', icon: 'wrench', label: 'Remédiation' },
  VERIFYING: { tone: 'warning', icon: 'warning', label: 'Vérification' },
  CLOSED: { tone: 'good', icon: 'check', label: 'Clôturé' },
  FAILED: { tone: 'critical', icon: 'cross', label: 'Échec' },
}

const seconds = (iso) => Date.parse(iso) / 1000

// Étapes de remédiation en direct du dernier incident (contrat : GET /incidents de remediation-engine).
// L'historique complet et le bilan de chaque incident sont dans le journal (IncidentJournal.jsx).
export default function Incidents({ data }) {
  const latest = data.items.slice(0, 1)
  return (
    <section className="card flex flex-col gap-3 p-4" aria-labelledby="titre-incidents">
      <h2 id="titre-incidents" className="font-semibold">Dernier incident et remédiation</h2>
      {!data.available && (
        <p className="muted text-sm">
          Moteur de remédiation pas encore déployé : les étapes (détection, action, vérification) s'afficheront ici en
          temps réel.
        </p>
      )}
      {data.available && data.items.length === 0 && <p className="muted text-sm">Aucun incident récent.</p>}
      <ol className="flex flex-col gap-4">
        {latest.map((incident) => {
          const status = STATUS[incident.status] ?? { tone: 'neutral', icon: 'question', label: incident.status }
          return (
            <li key={incident.id} className="flex flex-col gap-2">
              <p className="flex items-center gap-2 text-sm">
                <Icon name={status.icon} tone={status.tone} size={18} />
                <span className="font-semibold">{status.label}</span>
                <span className="muted">
                  {incident.trigger} - ouvert à {formatTime(seconds(incident.opened_at))}
                </span>
              </p>
              <ol className="ml-6 flex flex-col gap-1 border-l pl-4 text-sm" style={{ borderColor: 'var(--border)' }}>
                {(incident.steps ?? []).map((step) => (
                  <li key={`${step.at}-${step.action}`}>
                    <span className="muted tabular-nums">{formatTime(seconds(step.at))}</span> {step.action}
                    {step.result && <span className="muted"> : {step.result}</span>}
                  </li>
                ))}
              </ol>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
