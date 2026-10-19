import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/outfit/300.css'
import '@fontsource/outfit/400.css'
import '@fontsource/outfit/500.css'
import '@fontsource/outfit/600.css'
import '@fontsource/outfit/700.css'
import './styles/tokens.css'
import './styles/global.css'
import { ChatSessionsProvider } from './context/ChatSessionsContext'
import App from './App'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ChatSessionsProvider>
        <App />
      </ChatSessionsProvider>
    </BrowserRouter>
  </StrictMode>,
)
