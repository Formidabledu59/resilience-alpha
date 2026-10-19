import { useEffect, useRef, useState } from 'react'
import Layout from './components/Layout.jsx'
import { findRoute, pageTitle } from './routes.js'
import Paiement from './pages/Paiement.jsx'
import Confidentialite from './pages/Confidentialite.jsx'
import Cgu from './pages/Cgu.jsx'
import NotFound from './pages/NotFound.jsx'

const PAGES = { paiement: Paiement, confidentialite: Confidentialite, cgu: Cgu }

export default function App() {
  const [pathname, setPathname] = useState(window.location.pathname)
  const mainRef = useRef(null)
  const route = findRoute(pathname)
  const Page = route ? PAGES[route.page] : NotFound

  useEffect(() => {
    const onPop = () => setPathname(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    document.title = pageTitle(route)
    window.scrollTo(0, 0)
    // Accessibilité : le focus suit le changement de page
    mainRef.current?.querySelector('h1')?.focus()
  }, [route])

  return (
    <Layout mainRef={mainRef}>
      <Page />
    </Layout>
  )
}
