// Icônes d'état : une couleur de statut n'est jamais seule, elle accompagne une icône et un libellé
const PATHS = {
  check: 'M5 12.5 10 17.5 19 7.5',
  cross: 'M7 7 17 17 M17 7 7 17',
  warning: 'M12 4 21 19 3 19Z M12 10v4 M12 16.5v.5',
  wrench: 'M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-3z',
  question: 'M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14 M12 17v.5',
}

export const TONE_COLORS = {
  good: 'var(--good)',
  warning: 'var(--warning)',
  serious: 'var(--serious)',
  critical: 'var(--critical)',
  neutral: 'var(--neutral)',
}

export default function Icon({ name, tone = 'neutral', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="11" fill={TONE_COLORS[tone]} opacity="0.18" />
      <path d={PATHS[name]} fill="none" stroke={TONE_COLORS[tone]} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
