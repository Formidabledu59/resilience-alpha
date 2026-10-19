import { describe, expect, it } from 'vitest'
import { formatEuros, isSpam, parseAmount, validateLogin, validatePayment } from '../src/validation.js'

describe('parseAmount', () => {
  it('accepte le point ou la virgule et normalise à deux décimales', () => {
    expect(parseAmount('10')).toBe('10.00')
    expect(parseAmount('10,5')).toBe('10.50')
    expect(parseAmount(' 12.34 ')).toBe('12.34')
  })

  it('refuse les formats invalides', () => {
    for (const raw of ['', 'abc', '1.234', '-5', '1e3', '10,', null]) {
      expect(parseAmount(raw)).toBeNull()
    }
  })
})

describe('validatePayment', () => {
  it('produit le payload attendu par payment-api', () => {
    const { errors, payload } = validatePayment({ from: 'ACC-001', to: 'ACC-002', amount: '12,50' })
    expect(errors).toEqual({})
    expect(payload).toEqual({ from_account: 'ACC-001', to_account: 'ACC-002', amount: '12.50', currency: 'EUR' })
  })

  it('refuse des comptes identiques, un montant nul ou trop élevé', () => {
    expect(validatePayment({ from: 'ACC-001', to: 'ACC-001', amount: '5' }).errors.to).toBeDefined()
    expect(validatePayment({ from: 'ACC-001', to: 'ACC-002', amount: '0' }).errors.amount).toBeDefined()
    expect(validatePayment({ from: 'ACC-001', to: 'ACC-002', amount: '20000' }).errors.amount).toBeDefined()
    expect(validatePayment({ from: 'ACC-999', to: 'ACC-002', amount: '5' }).errors.from).toBeDefined()
  })
})

describe('formulaires', () => {
  it('exige identifiant et mot de passe', () => {
    expect(Object.keys(validateLogin({ username: ' ', password: '' }))).toEqual(['username', 'password'])
    expect(validateLogin({ username: 'demo', password: 'x' })).toEqual({})
  })

  it('détecte le champ piège anti-spam', () => {
    expect(isSpam('')).toBe(false)
    expect(isSpam('http://spam.example')).toBe(true)
  })

  it('formate les montants en euros sans espace insécable', () => {
    const text = formatEuros('1234.5')
    expect(text).toBe('1 234,50 €')
    expect(text).not.toMatch(new RegExp(`[${String.fromCodePoint(0xa0, 0x202f)}]`))
  })
})
