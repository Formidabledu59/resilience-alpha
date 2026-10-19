import Icon from './Icon.jsx'

// État des cibles Prometheus : icône + libellé UP / DOWN, jamais la couleur seule
export default function Targets({ targets }) {
  return (
    <section className="card flex flex-col gap-3 p-4" aria-labelledby="titre-cibles">
      <h2 id="titre-cibles" className="font-semibold">Services surveillés</h2>
      {targets.length === 0 ? (
        <p className="muted text-sm">Aucune donnée de Prometheus.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {targets.map((target) => (
            <li key={target.job} className="flex items-center gap-2 text-sm">
              <Icon name={target.up ? 'check' : 'cross'} tone={target.up ? 'good' : 'critical'} size={18} />
              <span className="flex-1">{target.job}</span>
              <span className="muted font-medium">{target.up ? 'UP' : 'DOWN'}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
