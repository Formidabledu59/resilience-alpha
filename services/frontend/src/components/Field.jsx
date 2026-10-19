// Champ de formulaire accessible : libellé lié, message d'erreur annoncé
export default function Field({ id, label, error, hint, children }) {
  const describedBy = [hint && `${id}-aide`, error && `${id}-erreur`].filter(Boolean).join(' ') || undefined
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="font-medium text-slate-900">{label}</label>
      {hint && <p id={`${id}-aide`} className="text-sm text-slate-700">{hint}</p>}
      {children({ id, 'aria-invalid': error ? 'true' : undefined, 'aria-describedby': describedBy })}
      {error && (
        <p id={`${id}-erreur`} className="text-sm font-medium text-red-700">{error}</p>
      )}
    </div>
  )
}

export const inputClass =
  'w-full rounded border border-slate-400 bg-white px-3 py-2 text-slate-900 aria-[invalid=true]:border-red-700'
