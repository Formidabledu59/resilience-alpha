import { useState } from 'react'
import Link from './Link.jsx'

const KEY = 'resilience-information-stockage'

function alreadyDismissed() {
  try {
    return localStorage.getItem(KEY) === 'vu'
  } catch {
    return false
  }
}

// Bandeau d'information : le site ne dépose aucun cookie et ne fait aucun suivi,
// il n'y a donc rien à accepter ou refuser (stockage strictement nécessaire).
export default function CookieBanner() {
  const [visible, setVisible] = useState(() => !alreadyDismissed())
  if (!visible) return null

  const dismiss = () => {
    try {
      localStorage.setItem(KEY, 'vu')
    } catch {
      // stockage indisponible : le bandeau réapparaîtra, sans gêner l'usage
    }
    setVisible(false)
  }

  return (
    <section
      aria-label="Information sur les cookies"
      className="fixed inset-x-0 bottom-0 border-t border-slate-300 bg-white shadow-lg"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-4 text-sm text-slate-800 sm:flex-row sm:items-center">
        <p className="flex-1">
          Ce site n'utilise aucun cookie, ni publicitaire ni de mesure d'audience. Seule votre session de connexion
          est gardée dans ce navigateur, le temps de l'onglet.{' '}
          <Link to="/confidentialite" className="underline">En savoir plus</Link>
        </p>
        <button
          type="button"
          onClick={dismiss}
          className="rounded border border-slate-400 px-4 py-2 font-medium text-slate-900 hover:bg-slate-100"
        >
          J'ai compris
        </button>
      </div>
    </section>
  )
}
