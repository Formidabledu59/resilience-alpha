import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import BackOfficeGate from './components/BackOfficeGate.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BackOfficeGate>
      <App />
    </BackOfficeGate>
  </StrictMode>,
)
