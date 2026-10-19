// Cohérence entre les pages déclarées, nginx, le sitemap et les liens du code :
// une page ajoutée d'un côté et oubliée de l'autre fait échouer le test (lien cassé).
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ROUTES, findRoute, pageTitle } from '../src/routes.js'

const root = join(import.meta.dirname, '..')
const read = (file) => readFileSync(join(root, file), 'utf8')
const paths = ROUTES.map((route) => route.path)

function sourceFiles(dir) {
  return readdirSync(join(root, dir)).flatMap((name) => {
    const rel = join(dir, name)
    return statSync(join(root, rel)).isDirectory() ? sourceFiles(rel) : [rel]
  })
}

describe('routes', () => {
  it('nginx sert exactement les pages déclarées', () => {
    const match = read('nginx.conf').match(/location ~ \^\/\(([^)]*)\)\?\/\?\$/)
    expect(match).not.toBeNull()
    const nginxPaths = ['/', ...match[1].split('|').map((name) => `/${name}`)]
    expect(nginxPaths.sort()).toEqual([...paths].sort())
  })

  it('le sitemap liste toutes les pages et seulement elles', () => {
    const locs = [...read('public/sitemap.xml').matchAll(/<loc>http:\/\/192\.168\.137\.1(\/[^<]*)<\/loc>/g)].map((m) => m[1])
    expect(locs.sort()).toEqual([...paths].sort())
  })

  it('chaque lien interne du code pointe vers une page ou un fichier existant', () => {
    const files = [...sourceFiles('src'), 'index.html', 'public/404.html']
    for (const file of files) {
      for (const [, target] of read(file).matchAll(/(?:to|href)="(\/[^"#]*)"/g)) {
        const exists = findRoute(target) !== null || statSync(join(root, 'public', target), { throwIfNoEntry: false })
        expect(exists, `${file} : lien cassé vers ${target}`).toBeTruthy()
      }
    }
  })

  it('normalise les chemins et produit un titre par page', () => {
    expect(findRoute('/cgu/')?.page).toBe('cgu')
    expect(findRoute('/inconnu')).toBeNull()
    expect(pageTitle(null)).toBe('Page introuvable - Resilience Alpha')
    expect(new Set(ROUTES.map(pageTitle)).size).toBe(ROUTES.length)
  })
})
