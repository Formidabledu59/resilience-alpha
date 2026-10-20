import { useState } from 'react'
import { clearAuth, identify, loadAuth, saveAuth, submitPassword } from '../biometrics.js'
import { nextAfterIdentify, nextAfterPassword } from '../backoffice.js'
import Habilitations from './Habilitations.jsx'

// Porte d'authentification du back-office : identifiant -> reconnaissance faciale -> mot de passe.
// Tant que l'accès n'est pas accordé, le dashboard n'est pas affiché.
export default function BackOfficeGate({ children }) {
  const [auth, setAuth] = useState(() => loadAuth())
  const [showHabilitations, setShowHabilitations] = useState(false)

  if (auth) {
    return (
      <div>
        <div className="flex items-center justify-end gap-3 px-4 py-2 text-sm" style={{ borderBottom: '1px solid var(--border)' }}>
          <span className="muted">Back-office : {auth.username}</span>
          <button type="button" className="underline" onClick={() => setShowHabilitations((v) => !v)}>
            {showHabilitations ? 'Supervision' : 'Habilitations'}
          </button>
          <button type="button" className="underline" onClick={() => { clearAuth(); setAuth(null) }}>
            Déconnexion
          </button>
        </div>
        {showHabilitations ? <Habilitations /> : children}
      </div>
    )
  }

  return <LoginFlow onGranted={(username) => setAuth(saveAuth(username))} />
}

function LoginFlow({ onGranted }) {
  const [step, setStep] = useState('username')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [feedback, setFeedback] = useState({ message: '', tone: '' })
  const [busy, setBusy] = useState(false)

  const submitUsername = async (event) => {
    event.preventDefault()
    if (!username.trim()) return
    setBusy(true)
    setFeedback({ message: 'Camera activee, reconnaissance en cours...', tone: 'ok' })
    try {
      const next = nextAfterIdentify(await identify(username.trim()))
      if (next.clearUsername) setUsername('')
      setStep(next.step)
      setFeedback({ message: next.message, tone: next.tone })
    } catch {
      setFeedback({ message: 'La passerelle biometrique ne repond pas.', tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  const submitPwd = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      const result = await submitPassword(username.trim(), password)
      const next = nextAfterPassword(result)
      setPassword('')
      if (next.step === 'granted') {
        onGranted(username.trim())
        return
      }
      setStep(next.step)
      setUsername('')
      setFeedback({ message: next.message, tone: next.tone })
    } catch {
      setFeedback({ message: 'La passerelle biometrique ne repond pas.', tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  // Au passage à l'étape mot de passe, l'identifiant reste celui saisi (non vidé)
  const input = 'w-full rounded border px-3 py-2'
  const inputStyle = { borderColor: 'var(--border)', background: 'var(--surface-1)', color: 'var(--text-primary)' }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <header>
        <h1 className="text-2xl font-bold">Back-office securise</h1>
        <p className="muted text-sm">Acces protege par reconnaissance faciale (consigne additionnelle 1).</p>
      </header>

      {step === 'username' ? (
        <form onSubmit={submitUsername} className="flex flex-col gap-3">
          <label htmlFor="bo-user" className="font-medium">Identifiant</label>
          <input id="bo-user" className={input} style={inputStyle} autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <button type="submit" disabled={busy} className="rounded px-4 py-3 font-semibold disabled:opacity-60" style={{ background: 'var(--cta-bg)', color: 'var(--cta-text)' }}>
            {busy ? 'Reconnaissance...' : 'Continuer'}
          </button>
        </form>
      ) : (
        <form onSubmit={submitPwd} className="flex flex-col gap-3">
          <label htmlFor="bo-pwd" className="font-medium">Mot de passe</label>
          <input id="bo-pwd" type="password" className={input} style={inputStyle} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
          <button type="submit" disabled={busy} className="rounded px-4 py-3 font-semibold disabled:opacity-60" style={{ background: 'var(--cta-bg)', color: 'var(--cta-text)' }}>
            {busy ? 'Verification...' : 'Se connecter'}
          </button>
        </form>
      )}

      {feedback.message && (
        <p role="status" className="rounded px-3 py-2 text-sm" style={{ background: 'var(--surface-1)', color: feedback.tone === 'error' ? 'var(--critical)' : 'var(--text-primary)' }}>
          {feedback.message}
        </p>
      )}
    </div>
  )
}

