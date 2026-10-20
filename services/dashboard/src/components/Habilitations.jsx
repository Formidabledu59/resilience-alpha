import { useCallback, useEffect, useState } from 'react'
import { enroll, listUsers, revoke } from '../biometrics.js'

// Gestion des habilitations : enrôler un visage (capture par la caméra du PC Hôte) et révoquer.
export default function Habilitations() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ username: '', password: '' })
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setUsers((await listUsers()).users ?? [])
    } catch {
      setMessage('Passerelle biometrique injoignable.')
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const onEnroll = async (event) => {
    event.preventDefault()
    if (!form.username.trim() || !form.password) return
    setBusy(true)
    setMessage('Regardez la camera : capture du visage en cours...')
    try {
      const result = await enroll(form.username.trim(), form.password)
      setMessage(result.status === 'enrolled'
        ? `Habilitation creee pour ${result.username} (${result.samples} images).`
        : 'Aucun visage detecte par la camera. Reessayez.')
      setForm({ username: '', password: '' })
      refresh()
    } catch {
      setMessage('Echec de l enrolement.')
    } finally {
      setBusy(false)
    }
  }

  const onRevoke = async (username) => {
    setBusy(true)
    try {
      await revoke(username)
      refresh()
    } finally {
      setBusy(false)
    }
  }

  const input = 'w-full rounded border px-3 py-2'
  const inputStyle = { borderColor: 'var(--border)', background: 'var(--surface-1)', color: 'var(--text-primary)' }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-6">
      <header>
        <h1 className="text-2xl font-bold">Habilitations</h1>
        <p className="muted text-sm">Visages autorises a acceder au back-office.</p>
      </header>

      <form onSubmit={onEnroll} className="card flex flex-col gap-3 p-4">
        <h2 className="font-semibold">Enroler un utilisateur</h2>
        <input className={input} style={inputStyle} placeholder="Identifiant" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <input className={input} style={inputStyle} type="password" placeholder="Mot de passe" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button type="submit" disabled={busy} className="rounded px-4 py-2 font-semibold disabled:opacity-60" style={{ background: 'var(--cta-bg)', color: 'var(--cta-text)' }}>
          {busy ? 'Capture...' : 'Enroler (capture camera)'}
        </button>
      </form>

      <section className="card p-4">
        <h2 className="mb-2 font-semibold">Utilisateurs autorises</h2>
        {users.length === 0 ? (
          <p className="muted text-sm">Aucun utilisateur enrole.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {users.map((u) => (
              <li key={u} className="flex items-center justify-between text-sm">
                <span>{u}</span>
                <button type="button" className="underline" style={{ color: 'var(--critical)' }} disabled={busy} onClick={() => onRevoke(u)}>
                  Revoquer
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {message && <p role="status" className="text-sm muted">{message}</p>}
    </div>
  )
}
