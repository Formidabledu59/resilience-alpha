import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { formatLatency, formatPercent, formatRate } from '../src/format.js'

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
})

describe('relais nginx', () => {
  it("chaque URL /api utilisée par le code est déclarée dans nginx.conf (pas d'appel cassé)", () => {
    const used = [...read('src/api.js').matchAll(/['`](\/api\/[a-z/_-]+)/g)].map((m) => m[1])
    expect(used.length).toBeGreaterThanOrEqual(4)
    const nginx = read('nginx.conf')
    for (const path of used) expect(nginx, path).toContain(`location = ${path} `)
  })

  it("le dashboard n'a aucun accès à Docker, Vault ou aux secrets", () => {
    const nginx = read('nginx.conf')
    for (const forbidden of ['socket-proxy', 'docker.sock', 'vault', 'alertmanager']) expect(nginx).not.toContain(forbidden)
  })
})
