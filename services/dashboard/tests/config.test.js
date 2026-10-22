import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { biometricsEnabled, loadConfig } from '../src/config.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => readFileSync(join(root, file), 'utf8')

describe('porte biométrique du back-office (consigne 1, désactivée par défaut)', () => {
  it("n'est active que si la configuration le demande explicitement", () => {
    expect(biometricsEnabled({ backofficeBiometrics: true })).toBe(true)
    expect(biometricsEnabled({ backofficeBiometrics: false })).toBe(false)
    expect(biometricsEnabled({ backofficeBiometrics: 'true' })).toBe(false)
    expect(biometricsEnabled({})).toBe(false)
    expect(biometricsEnabled(undefined)).toBe(false)
  })

  it('lit /config.json sans cache', async () => {
    const calls = []
    const fakeFetch = async (url, options) => {
      calls.push([url, options])
      return { ok: true, json: async () => ({ backofficeBiometrics: true }) }
    }
    expect(await loadConfig(fakeFetch)).toEqual({ backofficeBiometrics: true })
    expect(calls).toEqual([['/config.json', { cache: 'no-store' }]])
  })

  it('affiche la supervision si la configuration est absente ou illisible', async () => {
    const notFound = async () => ({ ok: false, json: async () => ({}) })
    const offline = async () => { throw new Error('réseau') }
    const invalid = async () => ({ ok: true, json: async () => { throw new SyntaxError('JSON') } })
    for (const fetchImpl of [notFound, offline, invalid]) {
      expect(biometricsEnabled(await loadConfig(fetchImpl))).toBe(false)
    }
  })

  it('nginx génère /config.json depuis BACKOFFICE_BIOMETRICS (template)', () => {
    const nginx = read('nginx.conf')
    expect(nginx).toContain('location = /config.json ')
    expect(nginx).toContain('{"backofficeBiometrics": ${BACKOFFICE_BIOMETRICS}}')
    expect(read('Dockerfile')).toContain('/etc/nginx/templates/default.conf.template')
  })

  it("le point d'entrée n'enveloppe l'application dans la porte que si elle est activée", () => {
    const main = read('src/main.jsx')
    expect(main).toContain('biometricsEnabled(config) ? <BackOfficeGate><App /></BackOfficeGate> : <App />')
  })
})
