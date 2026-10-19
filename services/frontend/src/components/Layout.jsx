import Link from './Link.jsx'
import CookieBanner from './CookieBanner.jsx'

export default function Layout({ mainRef, children }) {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#contenu" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Aller au contenu
      </a>
      <header className="border-b border-slate-200">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-4">
          <Link to="/" className="flex items-center gap-3 rounded text-slate-900 no-underline">
            <img src="/favicon.svg" alt="" width="32" height="32" />
            <span className="text-lg font-semibold">Resilience Alpha</span>
          </Link>
          <span className="ml-auto rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900">
            Données fictives
          </span>
        </div>
      </header>

      <main id="contenu" ref={mainRef} className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
        {children}
      </main>

      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-3xl flex-col gap-2 px-4 py-6 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
          <p>Démonstrateur pédagogique - workshop EPSI, groupe 16.</p>
          <nav aria-label="Informations légales" className="flex gap-4">
            <Link to="/confidentialite" className="underline hover:text-slate-900">Confidentialité</Link>
            <Link to="/cgu" className="underline hover:text-slate-900">CGU</Link>
          </nav>
        </div>
      </footer>

      <CookieBanner />
    </div>
  )
}
