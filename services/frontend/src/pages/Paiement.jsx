import { useCallback, useEffect, useState } from 'react'
import Field, { inputClass } from '../components/Field.jsx'
import { ApiError, clearSession, createTransaction, getAccount, loadSession, login, saveSession } from '../api.js'
import { ACCOUNTS, formatEuros, isSpam, validateLogin, validatePayment } from '../validation.js'

const primaryButton =
  'w-full rounded bg-brand px-4 py-3 font-semibold text-white hover:bg-brand-dark disabled:opacity-60 sm:w-auto'

function Honeypot({ value, onChange }) {
  return (
    <div className="honeypot" aria-hidden="true">
      <label htmlFor="site-web">Ne pas remplir ce champ</label>
      <input id="site-web" name="site-web" tabIndex={-1} autoComplete="off" value={value} onChange={onChange} />
    </div>
  )
}

function LoginForm({ onLogged }) {
  const [form, setForm] = useState({ username: '', password: '', trap: '' })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    if (isSpam(form.trap)) return
    const found = validateLogin(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    setBusy(true)
    setMessage('')
    try {
      const token = await login(form.username.trim(), form.password)
      onLogged(saveSession(form.username.trim(), token))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <Field id="identifiant" label="Identifiant" error={errors.username}>
        {(props) => (
          <input {...props} className={inputClass} autoComplete="username" value={form.username} onChange={update('username')} />
        )}
      </Field>
      <Field id="mot-de-passe" label="Mot de passe" error={errors.password}>
        {(props) => (
          <input {...props} type="password" className={inputClass} autoComplete="current-password" value={form.password} onChange={update('password')} />
        )}
      </Field>
      <Honeypot value={form.trap} onChange={update('trap')} />
      {message && <p role="alert" className="rounded bg-red-50 px-3 py-2 font-medium text-red-800">{message}</p>}
      <div>
        <button type="submit" className={primaryButton} disabled={busy}>
          {busy ? 'Connexion en cours...' : 'Se connecter'}
        </button>
      </div>
    </form>
  )
}

function PaymentForm({ session, onLogout }) {
  const [form, setForm] = useState({ from: ACCOUNTS[0], to: ACCOUNTS[1], amount: '', trap: '' })
  const [errors, setErrors] = useState({})
  const [result, setResult] = useState(null)
  const [balances, setBalances] = useState({})
  const [busy, setBusy] = useState(false)

  const handleError = useCallback(
    (error) => {
      if (error instanceof ApiError && error.status === 401) onLogout('Votre session a expiré. Reconnectez-vous.')
      else setResult({ kind: 'error', text: error.message })
    },
    [onLogout],
  )

  const refreshBalances = useCallback(async () => {
    try {
      const accounts = await Promise.all(ACCOUNTS.map((id) => getAccount(session.token, id)))
      setBalances(Object.fromEntries(accounts.map((account) => [account.id, account.balance])))
    } catch (error) {
      handleError(error)
    }
  }, [session.token, handleError])

  useEffect(() => {
    refreshBalances()
  }, [refreshBalances])

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    if (isSpam(form.trap)) return
    const { errors: found, payload } = validatePayment(form)
    setErrors(found)
    if (!payload) return
    setBusy(true)
    setResult(null)
    try {
      const transaction = await createTransaction(session.token, payload)
      setResult(
        transaction.status === 'COMPLETED'
          ? { kind: 'success', text: `Paiement accepté de ${formatEuros(payload.amount)}. Référence n° ${transaction.id}.` }
          : { kind: 'error', text: `Paiement refusé : solde insuffisant sur ${payload.from_account}. Référence n° ${transaction.id}.` },
      )
      if (transaction.status === 'COMPLETED') setForm({ ...form, amount: '' })
      refreshBalances()
    } catch (error) {
      handleError(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-slate-700">
        Connecté en tant que <strong className="text-slate-900">{session.username}</strong>.{' '}
        <button type="button" onClick={() => onLogout('')} className="underline hover:text-slate-900">
          Se déconnecter
        </button>
      </p>

      <section aria-labelledby="titre-soldes">
        <h2 id="titre-soldes" className="mb-2 text-lg font-semibold">Soldes des comptes fictifs</h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {ACCOUNTS.map((id) => (
            <li key={id} className="rounded border border-slate-200 p-4">
              <p className="text-sm text-slate-700">{id}</p>
              <p className="text-xl font-semibold">{balances[id] === undefined ? '-' : formatEuros(balances[id])}</p>
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Nouveau virement</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="compte-debit" label="Compte à débiter" error={errors.from}>
            {(props) => (
              <select {...props} className={inputClass} value={form.from} onChange={update('from')}>
                {ACCOUNTS.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
            )}
          </Field>
          <Field id="compte-credit" label="Compte à créditer" error={errors.to}>
            {(props) => (
              <select {...props} className={inputClass} value={form.to} onChange={update('to')}>
                {ACCOUNTS.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
            )}
          </Field>
        </div>
        <Field id="montant" label="Montant (EUR)" hint="Deux décimales au maximum, par exemple 12,50." error={errors.amount}>
          {(props) => (
            <input {...props} className={inputClass} inputMode="decimal" autoComplete="off" value={form.amount} onChange={update('amount')} />
          )}
        </Field>
        <Honeypot value={form.trap} onChange={update('trap')} />
        {result && (
          <p
            role={result.kind === 'success' ? 'status' : 'alert'}
            className={`rounded px-3 py-2 font-medium ${result.kind === 'success' ? 'bg-green-50 text-green-900' : 'bg-red-50 text-red-800'}`}
          >
            {result.text}
          </p>
        )}
        <div>
          <button type="submit" className={primaryButton} disabled={busy}>
            {busy ? 'Paiement en cours...' : 'Valider le paiement'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default function Paiement() {
  const [session, setSession] = useState(() => loadSession())
  const [notice, setNotice] = useState('')

  const logout = useCallback((message) => {
    clearSession()
    setSession(null)
    setNotice(message)
  }, [])

  return (
    <article className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 tabIndex={-1} className="text-2xl font-bold sm:text-3xl">Paiement sécurisé</h1>
        <p className="text-slate-700">
          Effectuez un virement entre deux comptes fictifs. Aucune donnée bancaire réelle n'est utilisée.
        </p>
      </header>
      {notice && <p role="status" className="rounded bg-amber-50 px-3 py-2 text-amber-900">{notice}</p>}
      {session ? (
        <PaymentForm session={session} onLogout={logout} />
      ) : (
        <LoginForm onLogged={(value) => { setNotice(''); setSession(value) }} />
      )}
    </article>
  )
}
