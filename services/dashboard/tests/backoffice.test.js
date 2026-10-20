import { describe, expect, it } from 'vitest'
import { nextAfterIdentify, nextAfterPassword } from '../src/backoffice.js'

describe('flux du back-office apres reconnaissance', () => {
  it('visage reconnu -> etape mot de passe', () => {
    const next = nextAfterIdentify({ status: 'recognized' })
    expect(next.step).toBe('password')
    expect(next.clearUsername).toBeFalsy()
  })

  it('visage non reconnu -> retour identifiant, champ vide', () => {
    const next = nextAfterIdentify({ status: 'not_recognized', attempts_left: 1 })
    expect(next.step).toBe('username')
    expect(next.clearUsername).toBe(true)
    expect(next.message).toMatch(/dernier essai/)
  })

  it('bloque -> message avec le delai', () => {
    const next = nextAfterIdentify({ status: 'locked', retry_in: 300 })
    expect(next.step).toBe('username')
    expect(next.message).toMatch(/300/)
  })
})

describe('flux du back-office apres mot de passe', () => {
  it('correct -> accorde', () => {
    expect(nextAfterPassword({ status: 'granted' }).step).toBe('granted')
  })

  it('faux -> on recommence depuis l identifiant', () => {
    const next = nextAfterPassword({ status: 'denied' })
    expect(next.step).toBe('username')
    expect(next.clearUsername).toBe(true)
  })
})
