// Tuile de chiffre clé : titre, valeur, précision. Pas de graphique, donc pas de couleur de série.
export default function StatTile({ label, value, detail }) {
  return (
    <div className="card flex flex-col gap-1 p-4">
      <p className="muted text-sm">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {detail && <p className="muted text-xs">{detail}</p>}
    </div>
  )
}
