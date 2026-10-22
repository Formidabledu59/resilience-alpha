import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import BackOfficeGate from './components/BackOfficeGate.jsx'
import { biometricsEnabled, loadConfig } from './config.js'
import './index.css'

// Porte biométrique du back-office seulement si BACKOFFICE_BIOMETRICS=true (voir config.js).
loadConfig().then((config) => {
  const app = biometricsEnabled(config) ? <BackOfficeGate><App /></BackOfficeGate> : <App />
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      {app}
    </StrictMode>,
  )
})
