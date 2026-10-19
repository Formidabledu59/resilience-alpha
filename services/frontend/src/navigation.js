// Routeur minimal (History API) : évite une dépendance pour trois pages
export function navigate(path) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}
