import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { reportUrl } from '../src/api.js'
import { formatDuration, formatLatency, formatPercent, formatRate } from '../src/format.js'

const root = join(import.meta.dirname, '..')
const read = (file) => readFileSync(join(root, file), 'utf8')
const NBSP = new RegExp(`[${String.fromCodePoint(0xa0, 0x202f)}]`)

describe('formatage français', () => {
  it('pourcentages, latences et débits lisibles, sans espace insécable', () => {
    expect(formatPercent(0.987)).toBe('98,7 %')
    expect(formatLatency(0.0834)).toBe('83 ms')
    expect(formatLatency(1.5)).toBe('1,50 s')
    expect(formatRate(0.2)).toBe('0,20 tx/s')
    expect(formatPercent(null)).toBe('-')
    for (const text of [formatPercent(0.5), formatRate(1234.5)]) expect(text).not.toMatch(NBSP)
  })

  it('durées de traitement des incidents', () => {
    expect(formatDuration(45)).toBe('45 s')
    expect(formatDuration(185)).toBe('3 min 05 s')
    expect(formatDuration(null)).toBe('-')
  })
})

describe('relais nginx', () => {
  it("chaque URL /api utilisée par le code est déclarée dans nginx.conf (pas d'appel cassé)", () => {
    // Les chemins qui se terminent par "/" sont suivis d'un identifiant : relais par expression régulière (test suivant)
    const used = [...read('src/api.js').matchAll(/['`](\/api\/[a-z/_-]+)/g)].map((m) => m[1]).filter((p) => !p.endsWith('/'))
    expect(used.length).toBeGreaterThanOrEqual(5)
    const nginx = read('nginx.conf')
    for (const path of used) expect(nginx, path).toContain(`location = ${path} `)
  })

  it("le rapport d'incident est relayé avec un identifiant strictement contrôlé", () => {
    expect(reportUrl('inc-2026-10-20-001')).toBe('/api/remediation/incidents/inc-2026-10-20-001/report')
    const location = read('nginx.conf').match(/location ~ "(\^\/api\/remediation\/incidents\/[^"]+)"/)
    expect(location).not.toBeNull()
    const pattern = new RegExp(location[1])
    expect(pattern.test(reportUrl('inc-2026-10-20-001'))).toBe(true)
    expect(pattern.test('/api/remediation/incidents/..%2F..%2Fetc/report')).toBe(false)
  })

  it('les appels biometriques passent par /api/biometrics/, relaye par nginx', () => {
    const bio = read('src/biometrics.js')
    expect(bio).toContain('/api/biometrics')
    // les endpoints appeles (identify, password, users, enroll)
    const endpoints = [...bio.matchAll(/call\(`?['`]?(\/[a-z]+)/g)].map((m) => m[1])
    expect(new Set(endpoints).size).toBeGreaterThanOrEqual(3)
    expect(read('nginx.conf')).toContain('location /api/biometrics/ ')
  })

  it("le dashboard n'a aucun accès à Docker, Vault ou aux secrets", () => {
    const nginx = read('nginx.conf')
    for (const forbidden of ['socket-proxy', 'docker.sock', 'vault', 'alertmanager']) expect(nginx).not.toContain(forbidden)
  })
})
