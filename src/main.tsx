import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Inter is served from this site (no Google Fonts request, nothing third-party to trust).
import '@fontsource-variable/inter/opsz.css'
import './index.css'
import './components/Phase2.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
