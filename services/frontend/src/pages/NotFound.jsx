import Link from '../components/Link.jsx'

export default function NotFound() {
  return (
    <article className="flex flex-col gap-4">
      <h1 tabIndex={-1} className="text-2xl font-bold sm:text-3xl">Page introuvable</h1>
      <p className="text-slate-700">L'adresse demandée n'existe pas ou a été déplacée.</p>
      <p>
        <Link to="/" className="font-semibold text-brand underline">Revenir au paiement</Link>
      </p>
    </article>
  )
}
