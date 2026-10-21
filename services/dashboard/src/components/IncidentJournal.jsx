import { reportUrl } from '../api.js'
import { formatDateTime, formatDuration } from '../format.js'
import Icon from './Icon.jsx'
import { STATUS } from './Incidents.jsx'

// Journal des incidents : pour chaque incident, l'état des lieux complet produit par remediation-engine
// (ce qui s'est passé, impact, erreurs observées, défense, chronologie, issue) et son rapport téléchargeable.

function Integrity({ integrity }) {
  if (!integrity) return null
  return (
    <p className="flex items-center gap-2 text-sm">
      <Icon name={integrity.ok ? 'check' : 'cross'} tone={integrity.ok ? 'good' : 'critical'} size={18} />
      {integrity.ok
        ? `Journal intègre : ${integrity.entries} entrée(s), chaîne SHA-256 vérifiée`
        : `Journal altéré : chaîne SHA-256 rompue à la ligne ${integrity.broken_at_line}`}
    </p>
  )
}

function Table({ caption, headers, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="muted">
            {headers.map((h) => (
              <th key={h} scope="col" className="py-1 pr-4 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} className="border-t align-top" style={{ borderColor: 'var(--border)' }}>
              {cells.map((cell, j) => (
                <td key={j} className="py-1 pr-4">{cell ?? '-'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  )
}

function IncidentDetail({ incident }) {
  const status = STATUS[incident.status] ?? { tone: 'neutral', icon: 'question', label: incident.status }
  const summary = incident.summary ?? {}
  const duration = summary.durations?.open_to_close_seconds
  const errors = incident.errors ?? []
  const defenses = incident.defenses ?? []
  return (
    <details className="rounded border p-3" style={{ borderColor: 'var(--border)' }}>
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <Icon name={status.icon} tone={status.tone} size={18} />
        <span className="font-semibold">{status.label}</span>
        <span>{incident.category_label ?? incident.trigger}</span>
        <span className="muted tabular-nums">
          {incident.id}, {formatDateTime(incident.opened_at)}
          {duration !== null && duration !== undefined && `, traité en ${formatDuration(duration)}`}
        </span>
      </summary>

      <div className="mt-3 flex flex-col gap-4">
        <Section title="Ce qui s'est passé">
          <p className="text-sm">{summary.what_happened ?? incident.trigger}</p>
        </Section>
        <Section title="Impact">
          <p className="text-sm">{summary.impact ?? '-'}</p>
        </Section>
        <Section title="Erreurs observées">
          {errors.length === 0 ? (
            <p className="muted text-sm">Aucune erreur relevée dans la fenêtre de l'incident.</p>
          ) : (
            <Table
              caption="Erreurs observées pendant l'incident"
              headers={['Type', 'Nombre', 'Signification', 'Détail']}
              rows={errors.map((e) => [e.type, e.count, e.meaning, e.detail])}
            />
          )}
        </Section>
        <Section title="Défense">
          {defenses.length === 0 ? (
            <p className="muted text-sm">Aucune défense enregistrée pour l'instant.</p>
          ) : (
            <Table
              caption="Mesures de défense"
              headers={['Couche', 'Action', 'Résultat']}
              rows={defenses.map((d) => [d.layer, d.action, d.result])}
            />
          )}
        </Section>
        <Section title="Chronologie">
          <ol className="flex flex-col gap-1 border-l pl-4 text-sm" style={{ borderColor: 'var(--border)' }}>
            {(incident.steps ?? []).map((step) => (
              <li key={`${step.at}-${step.action}`}>
                <span className="muted tabular-nums">{formatDateTime(step.at)}</span> {step.action}
                {step.result && <span className="muted"> : {step.result}</span>}
              </li>
            ))}
          </ol>
        </Section>
        <Section title="Issue">
          <p className="text-sm">{summary.outcome ?? '-'}</p>
        </Section>
        <p>
          <a className="text-sm font-semibold underline" href={reportUrl(incident.id)} download={`${incident.id}.md`}>
            Télécharger le rapport d'incident (Markdown)
          </a>
        </p>
      </div>
    </details>
  )
}

export default function IncidentJournal({ data }) {
  return (
    <section className="card flex flex-col gap-3 p-4" aria-labelledby="titre-journal">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h2 id="titre-journal" className="font-semibold">Journal des incidents</h2>
        <Integrity integrity={data.integrity} />
      </div>
      {!data.available && (
        <p className="muted text-sm">
          Moteur de remédiation non démarré : le journal (attaque, erreurs, défense, reprise) s'affichera ici.
        </p>
      )}
      {data.available && data.items.length === 0 && <p className="muted text-sm">Aucun incident enregistré.</p>}
      <div className="flex flex-col gap-2">
        {data.items.map((incident) => (
          <IncidentDetail key={incident.id} incident={incident} />
        ))}
      </div>
    </section>
  )
}
