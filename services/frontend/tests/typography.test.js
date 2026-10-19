// Règles typographiques du projet pour tous les textes affichés :
// pas de tiret cadratin ou demi-cadratin, pas de caractère "points de suspension",
// pas de guillemets courbes, pas d'espace insécable, pas de puces typographiques,
// pas de caractères invisibles issus d'un copier-coller.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join } from 'node:path'
import { expect, it } from 'vitest'

const root = join(import.meta.dirname, '..')
const SCANNED = ['src', 'public', 'index.html']
const TEXT_EXTENSIONS = new Set(['.js', '.jsx', '.html', '.css', '.svg', '.txt', '.xml', '.json'])

// Codes numériques plutôt que caractères littéraux : ce fichier reste lui-même "propre"
const FORBIDDEN = new Map(
  [
    [0x2014, 'tiret cadratin'],
    [0x2013, 'tiret demi-cadratin'],
    [0x2026, 'points de suspension en un caractère'],
    [0x201c, 'guillemet courbe ouvrant'],
    [0x201d, 'guillemet courbe fermant'],
    [0x2018, 'apostrophe courbe ouvrante'],
    [0x2019, 'apostrophe courbe'],
    [0x00a0, 'espace insécable'],
    [0x202f, 'espace fine insécable'],
    [0x2022, 'puce'],
    [0x25aa, 'puce carrée'],
    [0x2192, 'flèche'],
    [0x200b, 'espace sans chasse'],
    [0x200c, 'antiliant sans chasse'],
    [0x200d, 'liant sans chasse'],
    [0x2060, 'gluon de mots'],
    [0xfeff, 'BOM ou espace insécable sans chasse'],
  ].map(([code, name]) => [String.fromCodePoint(code), name]),
)

function files(path) {
  const full = join(root, path)
  if (statSync(full).isDirectory()) return readdirSync(full).flatMap((name) => files(join(path, name)))
  return TEXT_EXTENSIONS.has(extname(path)) ? [path] : []
}

it('aucun caractère typographique interdit dans les textes', () => {
  const problems = []
  for (const file of SCANNED.flatMap(files)) {
    readFileSync(join(root, file), 'utf8').split('\n').forEach((line, index) => {
      for (const [char, name] of FORBIDDEN) {
        if (line.includes(char)) problems.push(`${file}:${index + 1} ${name}`)
      }
    })
  }
  expect(problems).toEqual([])
})
