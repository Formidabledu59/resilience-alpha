import { navigate } from '../navigation.js'

// Lien interne : navigation sans rechargement, mais vrai <a href> (accessible, ouvrable dans un onglet)
export default function Link({ to, className = '', children }) {
  const onClick = (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return
    event.preventDefault()
    navigate(to)
  }
  return (
    <a href={to} onClick={onClick} className={className}>
      {children}
    </a>
  )
}
