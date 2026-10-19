// Source unique des pages du site. Les tests vérifient que nginx.conf et
// public/sitemap.xml déclarent exactement ces chemins (pas de lien cassé).

export const SITE_NAME = 'Resilience Alpha'

export const ROUTES = [
  { path: '/', page: 'paiement', title: 'Paiement sécurisé' },
  { path: '/confidentialite', page: 'confidentialite', title: 'Confidentialité et données personnelles' },
  { path: '/cgu', page: 'cgu', title: "Conditions générales d'utilisation" },
]

export const NOT_FOUND_TITLE = 'Page introuvable'

export function normalizePath(pathname) {
  if (!pathname) return '/'
  const trimmed = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  return trimmed || '/'
}

export function findRoute(pathname) {
  const path = normalizePath(pathname)
  return ROUTES.find((route) => route.path === path) ?? null
}

export function pageTitle(route) {
  return `${route ? route.title : NOT_FOUND_TITLE} - ${SITE_NAME}`
}
