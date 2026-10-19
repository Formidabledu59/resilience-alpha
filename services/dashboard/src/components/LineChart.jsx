import { useEffect, useRef, useState } from 'react'
import { formatTime } from '../format.js'

const HEIGHT = 180
const MARGIN = { top: 12, right: 12, bottom: 24, left: 56 }

// Courbe d'une seule série (le titre la nomme, pas de légende), réticule et infobulle au survol,
// vue tableau pour l'accessibilité. SVG fait main : pas de bibliothèque de graphiques à charger.
export default function LineChart({ title, points, format, yMin = 0, yMax, threshold, emptyText }) {
  const wrapper = useRef(null)
  const [width, setWidth] = useState(600)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)))
    observer.observe(wrapper.current)
    return () => observer.disconnect()
  }, [])

  const latest = points.at(-1)
  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom
  const top = Math.max(yMax ?? 0, threshold?.value ?? 0, ...points.map((p) => p.v)) || 1
  const t0 = points[0]?.t ?? 0
  const t1 = latest?.t ?? 1
  const x = (t) => MARGIN.left + (t1 === t0 ? plotW : ((t - t0) / (t1 - t0)) * plotW)
  const y = (v) => MARGIN.top + plotH - ((v - yMin) / (top - yMin)) * plotH
  const ticks = [yMin, (yMin + top) / 2, top]
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')

  const onMove = (event) => {
    if (points.length === 0) return
    const box = event.currentTarget.getBoundingClientRect()
    const px = event.clientX - box.left
    let nearest = 0
    points.forEach((p, i) => {
      if (Math.abs(x(p.t) - px) < Math.abs(x(points[nearest].t) - px)) nearest = i
    })
    setHover(nearest)
  }

  const point = hover !== null ? points[hover] : null

  return (
    <figure className="card flex flex-col gap-2 p-4">
      <figcaption className="flex items-baseline justify-between gap-2">
        <span className="font-semibold">{title}</span>
        <span className="muted text-sm tabular-nums">{latest ? format(latest.v) : '-'}</span>
      </figcaption>

      <div ref={wrapper} className="relative">
        {points.length === 0 ? (
          <p className="muted flex items-center justify-center text-sm" style={{ height: HEIGHT }}>{emptyText}</p>
        ) : (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={`${title}, dernière valeur ${format(latest.v)}`}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="var(--grid)" />
                <text x={MARGIN.left - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="var(--text-secondary)">
                  {format(tick)}
                </text>
              </g>
            ))}
            <text x={MARGIN.left} y={HEIGHT - 6} fontSize="11" fill="var(--text-secondary)">{formatTime(t0)}</text>
            <text x={width - MARGIN.right} y={HEIGHT - 6} textAnchor="end" fontSize="11" fill="var(--text-secondary)">{formatTime(t1)}</text>

            {threshold && (
              <g>
                <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(threshold.value)} y2={y(threshold.value)} stroke="var(--threshold)" strokeDasharray="4 4" />
                <text x={width - MARGIN.right} y={y(threshold.value) - 4} textAnchor="end" fontSize="11" fill="var(--text-secondary)">
                  {threshold.label}
                </text>
              </g>
            )}

            <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

            {point && (
              <g>
                <line x1={x(point.t)} x2={x(point.t)} y1={MARGIN.top} y2={MARGIN.top + plotH} stroke="var(--text-secondary)" strokeWidth="1" />
                <circle cx={x(point.t)} cy={y(point.v)} r="5" fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth="2" />
              </g>
            )}
            {/* zone de survol plus grande que la courbe */}
            <rect x={MARGIN.left} y={MARGIN.top} width={plotW} height={plotH} fill="transparent" />
          </svg>
        )}

        {point && (
          <div
            className="card pointer-events-none absolute px-2 py-1 text-xs shadow"
            style={{ left: Math.min(x(point.t) + 8, width - 140), top: 8 }}
          >
            <p className="muted">{formatTime(point.t)}</p>
            <p className="font-semibold tabular-nums">{format(point.v)}</p>
          </div>
        )}
      </div>

      {points.length > 0 && (
        <details className="text-sm">
          <summary className="muted cursor-pointer">Voir les valeurs</summary>
          <table className="mt-2 w-full text-left tabular-nums">
            <thead>
              <tr className="muted"><th className="font-normal">Heure</th><th className="font-normal">Valeur</th></tr>
            </thead>
            <tbody>
              {points.slice(-10).reverse().map((p) => (
                <tr key={p.t}><td>{formatTime(p.t)}</td><td>{format(p.v)}</td></tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </figure>
  )
}
