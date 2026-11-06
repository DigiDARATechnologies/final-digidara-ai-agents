import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Inter is served from this site (no Google Fonts request, nothing third-party to trust).
import '@fontsource-variable/inter/opsz.css'
// Plus Jakarta Sans: display/body face for the landing and login pages.
import '@fontsource-variable/plus-jakarta-sans/index.css'
import './index.css'
import './components/Phase2.css'
import './finalPass.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
