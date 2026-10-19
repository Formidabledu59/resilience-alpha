// Mise en forme commune des pages de texte (confidentialité, CGU)
export function Prose({ title, updated, children }) {
  return (
    <article className="flex flex-col gap-6 leading-relaxed text-slate-800">
      <header className="flex flex-col gap-2">
        <h1 tabIndex={-1} className="text-2xl font-bold text-slate-900 sm:text-3xl">{title}</h1>
        <p className="text-sm text-slate-700">Dernière mise à jour : {updated}</p>
      </header>
      {children}
    </article>
  )
}

export function Section({ title, children }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  )
}

export function List({ items }) {
  return (
    <ul className="list-disc pl-6">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  )
}
