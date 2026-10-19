import { useState } from 'react'
import { probe } from '../api.js'
import { formatLatency } from '../format.js'
import { PHASES } from '../status.js'
import Icon, { TONE_COLORS } from './Icon.jsx'

const STEPS = ['Avant', 'Pendant', 'Remédiation', 'Après']

// Bandeau principal : phase de la démonstration + l'unique bouton d'action de la page
export default function PhaseBanner({ phase }) {
  const info = PHASES[phase]
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const runProbe = async () => {
    setBusy(true)
    setResult(null)
    try {
      const body = await probe()
      setResult(
        body.ok
          ? { ok: true, text: `Transaction de contrôle réussie (n° ${body.transaction_id}, ${formatLatency(body.latency_seconds)}).` }
          : { ok: false, text: `Transaction de contrôle en échec : ${body.detail ?? body.status}.` },
      )
    } catch {
      setResult({ ok: false, text: 'Le canary ne répond pas : la transaction de contrôle est impossible.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="card flex flex-col gap-4 p-5"
      style={{ borderLeft: `6px solid ${TONE_COLORS[info.tone]}` }}
      aria-labelledby="titre-phase"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex flex-1 items-center gap-3">
          <Icon name={info.icon} tone={info.tone} size={36} />
          <div>
            <h2 id="titre-phase" className="text-xl font-semibold">{info.label}</h2>
            <ol className="muted mt-1 flex flex-wrap gap-x-3 text-sm" aria-label="Étapes de la démonstration">
              {STEPS.map((step) => (
                <li key={step} aria-current={step === info.step ? 'step' : undefined} className={step === info.step ? 'font-semibold' : ''} style={step === info.step ? { color: 'var(--text-primary)' } : undefined}>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
        <button
          type="button"
          onClick={runProbe}
          disabled={busy}
          className="rounded px-4 py-3 font-semibold disabled:opacity-60"
          style={{ background: 'var(--cta-bg)', color: 'var(--cta-text)' }}
        >
          {busy ? 'Transaction en cours...' : 'Lancer une transaction de contrôle'}
        </button>
      </div>
      {result && (
        <p role="status" className="flex items-center gap-2 text-sm">
          <Icon name={result.ok ? 'check' : 'cross'} tone={result.ok ? 'good' : 'critical'} size={18} />
          {result.text}
        </p>
      )}
    </section>
  )
}
