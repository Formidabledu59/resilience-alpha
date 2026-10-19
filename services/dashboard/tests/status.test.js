import { describe, expect, it } from 'vitest'
import { computePhase, scalar, toPoints, toTargets } from '../src/status.js'

const NOW = Date.parse('2026-10-19T12:00:00Z') / 1000
const base = { prometheusOk: true, canaryUp: 1, successRatio: 1, incidents: [], now: NOW }

describe('computePhase : les quatre temps de la démonstration', () => {
  it('avant : nominal quand le canari réussit', () => {
    expect(computePhase(base)).toBe('nominal')
  })

  it('pendant : incident si le canari échoue ou si le taux chute sous 80 %', () => {
    expect(computePhase({ ...base, canaryUp: 0 })).toBe('incident')
    expect(computePhase({ ...base, successRatio: 0.5 })).toBe('incident')
    expect(computePhase({ ...base, successRatio: 0.95 })).toBe('degraded')
  })

  it('remédiation : un incident actif prime sur le reste', () => {
    expect(computePhase({ ...base, canaryUp: 0, incidents: [{ status: 'REMEDIATING' }] })).toBe('remediation')
  })

  it('après : reprise confirmée pendant 10 minutes après la clôture', () => {
    const closed = (minutes) => [{ status: 'CLOSED', closed_at: new Date((NOW - minutes * 60) * 1000).toISOString() }]
    expect(computePhase({ ...base, incidents: closed(2) })).toBe('recovered')
    expect(computePhase({ ...base, incidents: closed(30) })).toBe('nominal')
  })

  it('inconnu si Prometheus ne répond pas ou si le canari n\'a jamais tourné', () => {
    expect(computePhase({ ...base, prometheusOk: false })).toBe('unknown')
    expect(computePhase({ ...base, canaryUp: null, successRatio: null })).toBe('unknown')
  })
})

describe('lecture des réponses Prometheus', () => {
  it('scalar ignore les résultats vides et NaN', () => {
    expect(scalar([{ value: [0, '0.5'] }])).toBe(0.5)
    expect(scalar([])).toBeNull()
    expect(scalar([{ value: [0, 'NaN'] }])).toBeNull()
  })

  it('toPoints et toTargets', () => {
    expect(toPoints([{ values: [[10, '1'], [25, 'NaN'], [40, '0.5']] }])).toEqual([{ t: 10, v: 1 }, { t: 40, v: 0.5 }])
    const targets = toTargets([{ metric: { job: 'loki' }, value: [0, '1'] }, { metric: { job: 'canary' }, value: [0, '0'] }])
    expect(targets).toEqual([{ job: 'canary', up: false }, { job: 'loki', up: true }])
  })
})
